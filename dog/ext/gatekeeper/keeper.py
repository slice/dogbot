import collections
import datetime
import logging
import typing

import discord

from lifesaver.utils import human_delta
from dog.formatting import represent
from . import checks
from .core import Bounce, Report

CHECKS = [getattr(checks, name) for name in checks.__all__]

INCORRECTLY_CONFIGURED = """Gatekeeper was configured incorrectly!

I'm not sure what to do, so just to be safe, I'm going to prevent this user from joining."""


class Keeper:
    """A class that gatekeeps users from guilds by processing checks."""

    def __init__(self, guild: discord.Guild, config, *, bot) -> None:
        self.bot = bot
        self.guild = guild
        self.config = config
        self.log = logging.getLogger(f'{__name__}.{guild.id}')

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
                await self.report(
                    member,
                    f'Failed to send bounce message to {represent(member)}.',
                )

    async def report(self, member: discord.Member, *args, **kwargs) -> typing.Optional[discord.Message]:
        """Send a message to the designated broadcast channel of a guild.

        If the bot doesn't have permission to send to the channel, the error
        will be silently dropped.
        """
        channel = self.broadcast_channel

        if not channel:
            self.log.warning('no broadcast channel for %d, cannot report', self.guild.id)
            return

        if channel.guild != member.guild:
            self.log.warning('broadcast channel is somewhere else, ignoring')
            return

        try:
            return await channel.send(*args, **kwargs)
        except discord.Forbidden:
            return

    async def bounce(self, member: discord.Member, reason: str):
        """Kick ("bounce") a user from the guild.

        An embed with the provided reason will be reported to the guild's
        broadcast channel.
        """
        await self.send_bounce_message(member)

        try:
            await member.kick(reason=f'Gatekeeper: {reason}')
        except discord.HTTPException as error:
            self.log.debug('failed to kick %d: %r', member.id, error)
            await self.report(member, f"Failed to kick {represent(member)}: `{error}`")
        else:
            embed = discord.Embed(color=discord.Color.red(), title=f'Bounced {represent(member)}')

            embed.add_field(name='Account Creation',
                            value=f'{human_delta(member.created_at)} ago\n{member.created_at}')

            embed.description = reason
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_thumbnail(url=member.avatar_url)

            await self.report(member, embed=embed)

    async def check(self, member: discord.Member):
        """Check a member and bounce them if necessary."""
        self.log.debug('%d: gatekeeping! (created_at=%s)', member.id, member.created_at)
        enabled_checks = self.config.get('checks', {})

        for check in CHECKS:
            check_name = check.__name__
            check_options = enabled_checks.get(check_name)

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
            except Bounce as bounce:
                self.log.debug('%d: failed to pass "%s" (err=%r)', member.id, check_name, bounce)
                await self.bounce(member, str(bounce))
                return False
            except Report as report:
                # something went wrong
                self.log.debug('error in config: %r', report)
                await self.report(member, str(report))
                await self.bounce(member, INCORRECTLY_CONFIGURED)
                return False

        self.log.debug('%d: passed all checks', member.id)
        return True
