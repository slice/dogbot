from typing import Optional

import discord
import lifesaver
from discord.ext import commands
from lifesaver.utils.formatting import pluralize


def format_guild(guild: discord.Guild) -> str:
    members = pluralize(member=len(guild.members))
    message = f'{guild.name} (`{guild.id}`, {members}, owned by {guild.owner} (`{guild.owner.id}`))'
    return discord.utils.escape_mentions(message)


class AdminMonitoringConfig(lifesaver.config.Config):
    guild_traffic: int


class AdminConfig(lifesaver.config.Config):
    monitoring_channels: AdminMonitoringConfig


@lifesaver.Cog.with_config(AdminConfig)
class Admin(lifesaver.Cog):
    def monitoring_channel(self, name: str) -> Optional[discord.TextChannel]:
        channel_id = getattr(self.config.monitoring_channels, name)
        return self.bot.get_channel(channel_id)

    @lifesaver.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        channel = self.monitoring_channel('guild_traffic')
        if not channel:
            return

        message = f'\N{large red circle} {format_guild(guild)}'
        await channel.send(message)

    @lifesaver.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        channel = self.monitoring_channel('guild_traffic')
        if not channel:
            return

        message = f'\N{large blue circle} {format_guild(guild)}'
        await channel.send(message)

    @lifesaver.group(hidden=True, invoke_without_command=True)
    @commands.is_owner()
    async def blacklist(self, ctx: lifesaver.Context, user: discord.User, *, reason=None):
        """Blacklist someone from using the bot."""
        await self.bot.blacklisted_storage.put(user.id, reason)
        await ctx.ok()

    @blacklist.command()
    @commands.is_owner()
    async def stats(self, ctx: lifesaver.Context):
        """Views blacklist statistics."""
        amount = len(self.bot.blacklisted_storage.all())
        await ctx.send(f'User(s) blocked: **{amount}**')

    @blacklist.command()
    @commands.is_owner()
    async def reason(self, ctx: lifesaver.Context, user: discord.User):
        """Views the reason for someone's blacklisting."""
        if user.id not in self.bot.blacklisted_storage:
            await ctx.send(f'{user} is not blacklisted.')
            return

        reason = self.bot.blacklisted_storage.get(user.id)
        if not reason:
            await ctx.send(f'{user} is blacklisted for no reason.')
        else:
            await ctx.send(f'{user} is blacklisted for reason: {reason}')

    @lifesaver.command(hidden=True)
    @commands.is_owner()
    async def unblacklist(self, ctx: lifesaver.Context, user: discord.User):
        """Unblacklists someone from using the bot."""
        try:
            await self.bot.blacklisted_storage.delete(user.id)
        except KeyError:
            pass
        await ctx.ok()


def setup(bot):
    bot.add_cog(Admin(bot))
