import discord
from discord.ext.commands import bot_has_permissions, guild_only, has_permissions
from lifesaver.bot import Cog, Context, command
from lifesaver.utils import escape_backticks, clean_mentions
from lifesaver.utils.timing import Ratelimiter

from dog.converters import SoftMember
from dog.formatting import represent


class Mod(Cog):
    """Moderation-related commands."""
    def __init__(self, bot):
        super().__init__(bot)
        self.auto_cooldown = Ratelimiter(1, 3)

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

    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return

        config = self.bot.guild_configs.get(message.guild)
        if not config:
            return
        autoresponses = config.get('autoresponses', {})

        for trigger, response in autoresponses.items():
            if trigger in message.content:
                if self.auto_cooldown.is_rate_limited(message.author.id, message.channel.id):
                    return
                cleaned_response = clean_mentions(message.channel, response)
                try:
                    await message.channel.send(cleaned_response)
                except discord.HTTPException:
                    pass

    @command()
    @guild_only()
    @bot_has_permissions(manage_roles=True)
    @has_permissions(manage_roles=True)
    async def vanity(self, ctx: Context, name, color: discord.Color = None, *targets: discord.Member):
        """Creates a vanity role."""
        try:
            role = await ctx.guild.create_role(
                name=name,
                color=color or discord.Color.default(),
                permissions=discord.Permissions.none(),
                reason=f'Vanity role created by {represent(ctx.author)}'
            )
        except discord.HTTPException as error:
            await ctx.send(f'Failed to create vanity role. Error: `{error}`')
            return

        if not targets:
            await ctx.ok()
            return

        name = escape_backticks(role.name)
        ctx.new_paginator(prefix='', suffix='')
        ctx += f'\U00002705 Created vanity role `{name}`.'

        for target in targets:
            try:
                await target.add_roles(role, reason=f'Vanity role auto-assign by {represent(ctx.author)}')
            except discord.HTTPException as error:
                ctx += f'\N{CROSS MARK} Failed to add `{name}` to {represent(target)}: {error}'
            else:
                ctx += f'\U00002705 Added `{name}` to {represent(target)}.'

        await ctx.send_pages()

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
