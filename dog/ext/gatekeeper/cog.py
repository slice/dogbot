import contextlib
import datetime
import io
import logging
from typing import Optional

import discord
from discord.ext import commands
from lifesaver.bot import Cog, Context, group
from lifesaver.utils import human_delta
from ruamel.yaml import YAML

from dog.ext.gatekeeper import checks
from dog.ext.gatekeeper.core import Block, Report
from dog.formatting import represent

CHECKS = list(map(checks.__dict__.get, checks.__all__))

log = logging.getLogger(__name__)


class Keeper:
    """A class that gatekeeps members from guilds."""
    def __init__(self, guild: discord.Guild, settings, *, bot) -> None:
        self.bot = bot
        self.guild = guild
        self.settings = settings

    @property
    def broadcast_channel(self) -> discord.TextChannel:
        """Return the broadcast channel for the associated guild."""
        channel_id = self.settings.get('broadcast_channel')
        if channel_id is None:
            return None

        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return None

        return channel

    @property
    def bounce_message(self):
        """Return the configured bounce message."""
        return self.settings.get('bounce_message')

    async def send_bounce_message(self, member: discord.Member):
        bounce_message = self.bounce_message

        if bounce_message is None:
            return

        try:
            await member.send(bounce_message)
        except discord.HTTPException:
            if self.settings.get('echo_dm_failures', False):
                await self.report(
                    member,
                    f'Failed to send bounce message to {represent(member)}.',
                )

    async def report(self, member: discord.Member, *args, **kwargs) -> Optional[discord.Message]:
        """Send a message to the designated broadcast channel of a guild."""
        channel = self.broadcast_channel

        if not channel:
            log.warning('no broadcast channel for %d, cannot report', self.guild.id)
            return None

        if channel.guild != member.guild:
            log.warning('broadcast channel is somewhere else, ignoring')
            return None

        try:
            return await channel.send(*args, **kwargs)
        except discord.Forbidden:
            return None

    async def block(self, member: discord.Member, reason: str):
        """Bounce a user from the guild."""
        await self.send_bounce_message(member)

        try:
            await member.kick(reason=f'Failed Gatekeeper check. {reason}')
        except discord.HTTPException as error:
            await self.report(
                member,
                f"Failed to kick {represent(member)}: `{error}`",
            )
        else:
            embed = discord.Embed(
                color=discord.Color.red(),
                title=f'Bounced {represent(member)}',
            )

            embed.add_field(
                name='Account Creation',
                value=f'{human_delta(member.created_at)} ago\n{member.created_at}'
            )

            embed.description = reason
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_thumbnail(url=member.avatar_url)

            await self.report(member, embed=embed)

    async def check(self, member: discord.Member):
        """Check a member and bounce them if necessary."""
        enabled_checks = self.settings.get('checks', {})

        for check in CHECKS:
            name = check.__name__
            check_options = enabled_checks.get(name)

            # check not present
            if check_options is None:
                continue

            if isinstance(check_options, dict):
                if not check_options.get('enabled', True):
                    continue
            elif isinstance(check_options, bool):
                if not check_options:
                    continue

            try:
                await check(member, check_options)
            except Block as block:
                await self.block(member, str(block))
                return False
            except Report as report:
                # something went wrong
                await self.report(member, str(report))
                await self.block(
                    member,
                    ("Gatekeeper was incorrectly configured. I'm not sure what "
                     "to do, so I'll just prevent this user from joining just "
                     "in case.")
                )
                return False

        return True


class Gatekeeper(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.yaml = YAML()

    async def __local_check(self, ctx: Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage()

        if not ctx.author.guild_permissions.ban_members:
            raise commands.CheckFailure(
                'You can only manage Gatekeeper if you have the "Ban Members" '
                'permission.'
            )

        return True

    @property
    def dashboard_link(self):
        return self.bot.config.dashboard_link

    def settings(self, guild: discord.Guild):
        """Return Gatekeeper settings for a guild."""
        config = self.bot.guild_configs.get(guild) or {}
        return config.get('gatekeeper', {})

    @contextlib.asynccontextmanager
    async def edit_config(self, guild: discord.Guild):
        config = self.bot.guild_configs.get(guild) or {}
        yield config['gatekeeper']

        with io.StringIO() as buffer:
            self.yaml.indent(mapping=4, sequence=6, offset=4)
            self.yaml.dump(config, buffer)
            await self.bot.guild_configs.write(guild, buffer.getvalue())

    async def on_member_join(self, member: discord.Member):
        await self.bot.wait_until_ready()

        settings = self.settings(member.guild)

        if not settings.get('enabled', False):
            return

        keeper = Keeper(member.guild, settings, bot=self.bot)

        overridden = settings.get('allowed_users', [])
        is_overridden = str(member) in overridden or member.id in overridden

        if not is_overridden:
            is_allowed = await keeper.check(member)
            if not is_allowed:
                return

        if settings.get('quiet', False):
            return

        embed = discord.Embed(
            color=discord.Color.green(),
            title=f'{represent(member)} has joined',
            description='This user has passed all Gatekeeper checks.'
        )

        if is_overridden:
            embed.description = 'This user has been specifically allowed into this server.'

        embed.set_thumbnail(url=member.avatar_url)
        embed.timestamp = datetime.datetime.utcnow()

        await keeper.report(member, embed=embed)

    @group(aliases=['gk'], hollow=True)
    async def gatekeeper(self, ctx: Context):
        """
        Manages Gatekeeper.

        Gatekeeper is an advanced mechanism of Dogbot that allows you to screen member joins in realtime,
        and automatically kick those who don't fit a certain criteria. Only users who can ban can use it.
        This is very useful when your server is undergoing raids, unwanted attention, unwanted members, etc.
        """

    @gatekeeper.command()
    async def toggle(self, ctx: Context):
        """Toggles Gatekeeper."""
        settings = self.settings(ctx.guild)

        if not settings:
            await ctx.send("Gatekeeper is unconfigured.")
            return

        async with self.edit_config(ctx.guild) as config:
            config['enabled'] = not config['enabled']

        if config['enabled']:
            state = 'enabled'
        else:
            state = 'disabled'

        await ctx.send(f'Gatekeeper is now {state}.')

    @gatekeeper.command()
    async def status(self, ctx: Context):
        """Views the current status of Gatekeeper."""
        enabled = self.settings(ctx.guild).get('enabled', False)

        if enabled:
            description = 'Incoming members must pass Gatekeeper checks to join.'
        else:
            description = 'Anyone can join.'

        link = f'{self.dashboard_link}#/guild/{ctx.guild.id}'
        description += f' Use [the web dashboard]({link}) to configure gatekeeper.'

        embed = discord.Embed(
            color=discord.Color.green()
            if not enabled else discord.Color.red(),
            title='Gatekeeper is ' + ('enabled' if enabled else 'disabled') + '.',
            description=description
        )

        await ctx.send(embed=embed)
