import datetime
import inspect
import io
import logging
from typing import Optional

import discord
from discord.ext import commands
from lifesaver.bot import Cog, Context, group
from lifesaver.utils import human_delta
from ruamel.yaml import YAML

from dog.ext.gatekeeper import checks
from dog.ext.gatekeeper.core import Block, Check, Report
from dog.formatting import represent

log = logging.getLogger(__name__)


def thing_is_check(thing) -> bool:
    # only care about classes
    if not inspect.isclass(thing):
        return False

    # only look at subclasses of check
    if not issubclass(thing, Check):
        return False

    # ignore the base class
    return thing is not Check


# dir() the checks module to create a list of all checks on the fly
GATEKEEPER_CHECKS = [
    getattr(checks, check) for check in dir(checks)
    if thing_is_check(getattr(checks, check))
]


class Gatekeeper(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.yaml = YAML(typ='safe')

    async def __local_check(self, ctx: Context):
        return ctx.guild and ctx.author.guild_permissions.ban_members

    @property
    def dashboard_link(self):
        return self.bot.config.dashboard_link

    def settings(self, guild: discord.Guild):
        """Fetch Gatekeeper settings for a guild."""
        config = self.bot.guild_configs.get(guild) or {}
        return config.get('gatekeeper') or {}

    async def report(self, member, *args, **kwargs) -> Optional[discord.Message]:
        """Send a message to the broadcast channel for this guild."""
        settings = self.settings(member.guild)

        try:
            channel_id = settings.get('broadcast_channel')
            broadcast_channel = self.bot.get_channel(channel_id)

            if not broadcast_channel:
                log.warning("Couldn't find broadcast channel for guild %d.", member.guild.id)
                return None
            elif broadcast_channel.guild != member.guild:
                log.warning("Assigned broadcast channel wasn't here, ignoring.")
                return None

            return await broadcast_channel.send(*args, **kwargs)
        except (TypeError, discord.Forbidden):
            pass
        return None

    async def block(self, member: discord.Member, reason: str):
        """Bounce a user from the guild."""
        settings = self.settings(member.guild)

        if 'bounce_message' in settings:
            try:
                await member.send(settings['bounce_message'])
            except discord.HTTPException:
                pass

        try:
            await member.kick(reason=f'Failed Gatekeeper check: {reason}')
        except discord.Forbidden:
            await self.report(member, f"\N{CROSS MARK} I couldn't kick {represent(member)}.")
        else:
            embed = discord.Embed(
                color=discord.Color.red(),
                title=f'Bounced {represent(member)}'
            )
            embed.add_field(
                name='Account creation',
                value=f'{human_delta(member.created_at)} ago\n{member.created_at}'
            )
            embed.add_field(name='Reason', value=reason)
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_thumbnail(url=member.avatar_url)

            await self.report(member, embed=embed)

    async def screen(self, member: discord.Member):
        settings = self.settings(member.guild)

        enabled_checks = settings.get('checks', {})
        for check in GATEKEEPER_CHECKS:
            if check.key not in enabled_checks:
                continue

            try:
                parameter = enabled_checks[check.key]
                check_instance = check(self, member)
                await check_instance.check(parameter)
            except Block as block_exc:
                await self.block(member, str(block_exc))
                return False
            except Report as report_exc:
                await self.report(member, str(report_exc))

        return True

    async def on_member_join(self, member: discord.Member):
        await self.bot.wait_until_ready()

        settings = self.settings(member.guild)

        if not settings.get('enabled', False):
            return

        passthrough_users = settings.get('allowed_users', [])
        passthrough = str(member) in passthrough_users or member.id in passthrough_users

        if not passthrough and not await self.screen(member):
            return

        embed = discord.Embed(
            color=discord.Color.green(),
            title=f'{represent(member)} has joined',
            description='This user has passed all Gatekeeper checks.'
        )
        embed.set_thumbnail(url=member.avatar_url)
        embed.timestamp = datetime.datetime.utcnow()

        await self.report(member, embed=embed)

    @group(aliases=['gk'], hollow=True)
    async def gatekeeper(self, ctx: Context):
        """
        Manages Gatekeeper.

        Gatekeeper is an advanced mechanism of Dogbot that allows you to screen member joins in realtime,
        and automatically kick those who don't fit a certain criteria. Only users who can ban can use it.
        This is very useful when your server is undergoing raids, unwanted attention, unwanted members, etc.
        """

    @gatekeeper.command()
    @commands.has_permissions(ban_members=True)
    async def toggle(self, ctx: Context):
        """Toggles Gatekeeper."""
        settings = self.settings(ctx.guild)

        if not settings:
            await ctx.send("Gatekeeper is unconfigured.")

        config = ctx.bot.guild_configs.get(ctx.guild)
        config['gatekeeper']['enabled'] = not config['gatekeeper']['enabled']
        with io.StringIO() as buf:
            self.yaml.dump(config, buf)
            await ctx.bot.guild_configs.write(ctx.guild, buf.getvalue())

        if config['gatekeeper']['enabled']:
            state = 'enabled'
        else:
            state = 'disabled'

        await ctx.send(f'Gatekeeper is now {state}.')

    @gatekeeper.command()
    async def status(self, ctx: Context):
        """Views the current status of Gatekeeper."""
        enabled = self.settings(ctx.guild).get('enabled', False)

        if enabled:
            description = "Incoming members must pass Gatekeeper checks to join."
        else:
            description = "Anyone can join."

        link = self.dashboard_link + f'#/guild/{ctx.guild.id}'
        description += f' Use [the web dashboard]({link}) to configure gatekeeper.'

        embed = discord.Embed(
            color=discord.Color.green()
            if not enabled else discord.Color.red(),
            title='Gatekeeper is ' + ('enabled' if enabled else 'disabled') + '.',
            description=description
        )

        await ctx.send(embed=embed)
