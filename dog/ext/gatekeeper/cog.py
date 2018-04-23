import inspect
import logging
import datetime
from typing import Optional

import discord
from discord import Member, Embed
from discord.ext import commands
from lifesaver.bot import Cog, Context
from lifesaver.utils import human_delta

from dog.ext.gatekeeper import checks
from dog.ext.gatekeeper.core import Block, Report, Check
from dog.formatting import represent

log = logging.getLogger(__name__)

GATEKEEPER_CHECKS = [
    getattr(checks, check) for check in dir(checks)
    if inspect.isclass(getattr(checks, check)) and issubclass(getattr(checks, check), Check) and
    getattr(checks, check) is not Check
]


class Gatekeeper(Cog):
    async def __local_check(self, ctx: Context):
        return ctx.guild and ctx.author.guild_permissions.ban_members

    def settings(self, guild: discord.Guild):
        config = self.bot.guild_configs.get(guild) or {}
        return config.get('gatekeeper') or {}

    async def on_member_join(self, member: Member):
        if not self.settings(member.guild).get('enabled', False):
            return

        settings = self.settings(member.guild)

        async def report(*args, **kwargs) -> Optional[discord.Message]:
            """Sends a message to the broadcast channel for this guild."""
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

        async def block(reason: str):
            """Bounces a user from this guild."""

            if 'bounce_message' in settings:
                try:
                    await member.send(settings['bounce_message'])
                except discord.HTTPException:
                    pass

            try:
                await member.kick(reason=f'Gatekeeper check(s) failed ({reason})')
            except discord.Forbidden:
                await report(
                    f"\N{CROSS MARK} Couldn't kick {represent(member)}, no permissions. You will have to kick them "
                    "manually."
                )
            else:
                # report
                embed = Embed(color=discord.Color.red(), title=f'Bounced {represent(member)}')
                embed.add_field(
                    name='Account creation',
                    value=f'{human_delta(member.created_at)} ago\n{member.created_at}'
                )
                embed.add_field(name='Reason', value=reason)
                embed.timestamp = datetime.datetime.utcnow()
                embed.set_thumbnail(url=member.avatar_url)
                await report(embed=embed)

        enabled_checks = settings.get('checks', {})
        for check in GATEKEEPER_CHECKS:
            if check.key not in enabled_checks:
                continue

            try:
                await check().check(enabled_checks[check.key], member)
            except Block as block_exc:
                await block(str(block_exc))
                return
            except Report as report_exc:
                await report(str(report_exc))

        # this person has passed all checks
        embed = Embed(
            color=discord.Color.green(),
            title=f'{represent(member)} joined',
            description='This user has passed all Gatekeeper checks and has joined the server.'
        )
        embed.set_thumbnail(url=member.avatar_url)
        embed.timestamp = datetime.datetime.utcnow()
        await report(embed=embed)

    @commands.group(aliases=['gk'])
    async def gatekeeper(self, ctx: commands.Context):
        """
        Manages Gatekeeper.

        Gatekeeper is an advanced mechanism of Dogbot that allows you to screen member joins in realtime,
        and automatically kick those who don't fit a certain criteria. Only users who can ban can use it.
        This is very useful when your server is undergoing raids, unwanted attention, unwanted members, etc.
        """
        if ctx.invoked_subcommand is None:
            return await ctx.send(
                f'You need to specify a valid subcommand to run. For help, run `{ctx.prefix}help gk`.'
            )

    @gatekeeper.command()
    async def status(self, ctx: Context):
        """Views the current status of Gatekeeper."""
        enabled = self.settings(ctx.guild).get('enabled', False)

        description = "I'm not screening member joins at the moment." if not enabled else "I'm screening member joins."
        embed = Embed(
            color=discord.Color.green()
            if not enabled else discord.Color.red(),
            title='Gatekeeper is ' + ('active' if enabled else 'disabled') + '.',
            description=description + '\nConfigure Gatekeeper through the web dashboard.'
        )

        await ctx.send(embed=embed)
