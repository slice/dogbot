import collections
import logging
import typing

import discord
from lifesaver.utils.timing import Ratelimiter
from dog.formatting import represent
from . import checks
from .core import CheckFailure, Ban, Bounce, Report, create_embed

ALL_CHECKS = [getattr(checks, name) for name in checks.__all__]

INCORRECTLY_CONFIGURED = """Gatekeeper was configured incorrectly!

I'm not sure what to do, so just to be safe, I'm going to prevent this user from joining."""

Threshold = collections.namedtuple('Threshold', 'rate per')


def parse_threshold(threshold: str) -> Threshold:
    try:
        rate, per = threshold.split('/')
        if '' in (rate, per):
            raise TypeError('Invalid threshold syntax')
        return Threshold(rate=int(rate), per=float(per))
    except ValueError:
        return TypeError('Invalid threshold syntax')


class Keeper:
    """A class that gatekeeps users from guilds by processing checks."""

    def __init__(self, guild: discord.Guild, config, *, bot) -> None:
        self.bot = bot
        self.guild = guild
        self.log = logging.getLogger(f'{__name__}.{guild.id}')

        self.config = None
        self.ban_ratelimiter = None
        self.update_config(config)

    def __repr__(self):
        return f'<Keeper guild={self.guild!r}>'

    def _setup_ratelimiter(self, config_key, ratelimiter_attr):
        """Set up a Ratelimiter attribute on this Keeper from a threshold
        specified in the config with a special syntax ("rate/per").
        """
        try:
            threshold = parse_threshold(self.config[config_key])
            ratelimiter = Ratelimiter(threshold.rate, threshold.per)
            setattr(self, ratelimiter_attr, ratelimiter)
        except (KeyError, ValueError):
            setattr(self, ratelimiter_attr, None)

    def update_config(self, config):
        """Update this Keeper to use a new config."""
        self.config = config
        self._setup_ratelimiter('ban_threshold', 'ban_ratelimiter')

    @property
    def broadcast_channel(self) -> discord.TextChannel:
        """Return the broadcast channel for the associated guild."""
        channel_id = self.config.get('broadcast_channel')
        if channel_id is None:
            return None

        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return None

        return channel

    @property
    def bounce_message(self):
        """Return the configured bounce message."""
        return self.config.get('bounce_message')

    async def send_bounce_message(self, member: discord.Member):
        """Send a bounce message to a member."""
        bounce_message = self.bounce_message

        if bounce_message is None:
            return

        try:
            await member.send(bounce_message)
        except discord.HTTPException:
            if self.config.get('echo_dm_failures', False):
                await self.report(f'Failed to send bounce message to {represent(member)}.')

    async def report(self, *args, **kwargs) -> typing.Optional[discord.Message]:
        """Send a message to the designated broadcast channel of a guild.

        If the bot doesn't have permission to send to the channel, the error
        will be silently dropped.
        """
        channel = self.broadcast_channel

        if not channel:
            self.log.warning('no broadcast channel, cannot report')
            return

        if channel.guild != self.guild:
            self.log.warning('broadcast channel is somewhere else, ignoring')
            return

        try:
            return await channel.send(*args, **kwargs)
        except discord.HTTPException as error:
            self.log.warning('unable to send message to %r: %r', channel, error)

    async def _ban_reverse_prompt(self, message, banned):
        unban_emoji = self.bot.emoji('gatekeeper.unban')
        await message.add_reaction(unban_emoji)

        def check(reaction, member):
            if not isinstance(member, discord.Member) or member.bot:
                return False
            can_ban = member.guild_permissions.ban_members
            return reaction.message.id == message.id and reaction.emoji == unban_emoji and can_ban

        _reaction, user = await self.bot.wait_for('reaction_add', check=check)

        try:
            await banned.unban(reason=f'Gatekeeper: Ban was reversed by {represent(user)}')
        except discord.HTTPException as error:
            await self.report(f'Cannot reverse the ban of {represent(banned)}: `{error}`')
        else:
            await self.report(f'The ban of {represent(banned)} was reversed by {represent(user)}.')

    async def ban(self, member: discord.Member, reason: str):
        """Bans a user from the guild.

        An embed with the provided ban reason will be reported to the guild's
        broadcast channel.
        """
        try:
            await member.ban(delete_message_days=0, reason=f'Gatekeeper: {reason}')
        except discord.HTTPException as error:
            self.log.debug('failed to ban %d: %r', member.id, error)
            await self.report(f'Failed to ban {represent(member)}: `{error}`')
        else:
            embed = create_embed(
                member, color=discord.Color.purple(),
                title=f'Banned {represent(member)}', reason=reason)
            message = await self.report(embed=embed)
            # in case mods wants to reverse the ban, present a reaction prompt
            self.bot.loop.create_task(self._ban_reverse_prompt(message, member))

    async def bounce(self, member: discord.Member, reason: str):
        """Kick ("bounce") a user from the guild.

        An embed with the provided bounce reason will be reported to the guild's
        broadcast channel.
        """
        await self.send_bounce_message(member)

        try:
            await member.kick(reason=f'Gatekeeper: {reason}')
        except discord.HTTPException as error:
            self.log.debug('failed to kick %d: %r', member.id, error)
            await self.report(f'Failed to kick {represent(member)}: `{error}`')
        else:
            embed = create_embed(
                member, color=discord.Color.red(),
                title=f'Bounced {represent(member)}', reason=reason)
            await self.report(embed=embed)

    async def _perform_checks(self, member: discord.Member, checks):
        for check in ALL_CHECKS:
            check_name = check.__name__
            check_options = checks.get(check_name)

            # check isn't present in the config
            if check_options is None:
                continue

            if isinstance(check_options, collections.Mapping):
                # enabled subkey of check options
                if not check_options.get('enabled', False):
                    continue
            elif isinstance(check_options, bool):
                # legacy behavior: the "check options" is simply a boolean
                # denoting whether the check is enabled or not
                if not check_options:
                    continue

            try:
                await check(member, check_options)
            except CheckFailure as error:
                # inject check details into the error
                error.check_name = check_name
                error.check = check
                raise error from None

    async def check(self, member: discord.Member):
        """Check a member and bounce or ban them if necessary."""
        self.log.debug('%d: gatekeeping! (created_at=%s)', member.id, member.created_at)

        if self.ban_ratelimiter and self.ban_ratelimiter.is_rate_limited(member.id):
            # user is joining too fast!
            self.log.debug('%d: is joining too fast, banning', member.id)
            await self.ban(member, 'Joining too quickly')
            return False

        async def handle_misconfiguration(report):
            self.log.debug('error in config: %r', report)
            await self.report(str(report))
            await self.bounce(member, INCORRECTLY_CONFIGURED)

        # perform bannable checks
        try:
            bannable_checks = self.config.get('bannable_checks', {})
            await self._perform_checks(member, bannable_checks)
        except CheckFailure as error:
            self.log.debug('%d: banning, failed to pass bannable checks (failed "%s", err=%r)',
                           member.id, error.check_name, error)
            await self.ban(member, str(error))
            return False
        except Report as report:
            await handle_misconfiguration(report)
            return False

        # perform regular checks
        try:
            enabled_checks = self.config.get('checks', {})
            await self._perform_checks(member, enabled_checks)
        except Ban as ban:
            self.log.debug('%d: banning (err=%r)', member.id, ban)
            await self.ban(member, str(ban))
            return False
        except Bounce as bounce:
            self.log.debug('%d: failed to pass "%s" (err=%r)', member.id, bounce.check_name, bounce)
            await self.bounce(member, str(bounce))
            return False
        except Report as report:
            await handle_misconfiguration(report)
            return False

        self.log.debug('%d: passed all checks', member.id)
        return True
