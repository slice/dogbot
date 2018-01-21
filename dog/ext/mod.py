import discord
from discord.ext.commands import guild_only, bot_has_permissions, has_permissions
from lifesaver.bot import Cog, command, Context

from dog.converters import SoftMember
from dog.formatting import represent


class Mod(Cog):
    """Moderation-related commands."""
    @command()
    @guild_only()
    @bot_has_permissions(ban_members=True)
    @has_permissions(ban_members=True)
    async def ban(self, ctx: Context, target: SoftMember, *, reason):
        """Bans someone."""
        try:
            reason = f'Banned by {represent(ctx.author)}: {reason or "No reason."}'
            await ctx.guild.ban(target, reason=reason)
        except discord.Forbidden:
            await ctx.send(f"I can't ban {target}.")
        else:
            await ctx.send(f'\N{OK HAND SIGN} Banned {represent(target)}.')

    @command()
    @guild_only()
    @bot_has_permissions(ban_members=True)
    @has_permissions(ban_members=True)
    async def softban(self, ctx: Context, target: discord.Member, *, reason):
        """Bans then immediately unbans someone."""
        try:
            reason = f'Softbanned by {represent(ctx.author)}: {reason or "No reason."}'
            await target.ban(reason=reason)
            await target.unban(reason=reason)
        except discord.Forbidden:
            await ctx.send(f"I can't ban {target}.")
        else:
            await ctx.send(f'\N{OK HAND SIGN} Softbanned {represent(target)}.')

    @command()
    @guild_only()
    @bot_has_permissions(manage_roles=True)
    @has_permissions(manage_roles=True)
    async def block(self, ctx: Context, *, target: discord.Member):
        """Blocks someone from this channel."""
        reason = f'Blocked by {represent(ctx.author)}.'
        await ctx.channel.set_permissions(target, read_messages=False, reason=reason)
        await ctx.send(f'\N{OK HAND SIGN} Blocked {represent(target)}.')

    @command()
    @guild_only()
    @bot_has_permissions(manage_roles=True)
    @has_permissions(manage_roles=True)
    async def unblock(self, ctx: Context, *, target: discord.Member):
        """Unblocks someone from this channel."""
        reason = f'Unblocked by {represent(ctx.author)}.'
        overwrite = ctx.channel.overwrites_for(target)
        can_read = overwrite.read_messages

        if can_read is None or can_read:
            await ctx.send(f'{represent(target)} is not blocked from this channel.')
            return

        # neutral
        overwrite.read_messages = None

        # if the resulting permission overwrite is empty, just delete the overwrite entirely to prevent clutter.
        if overwrite.is_empty():
            await ctx.channel.set_permissions(target, overwrite=None, reason=reason)
        else:
            await ctx.channel.set_permissions(target, overwrite=overwrite, reason=reason)

        await ctx.send(f'\N{OK HAND SIGN} Unblocked {represent(target)}.')


def setup(bot):
    bot.add_cog(Mod(bot))
