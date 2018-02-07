import aiohttp
import discord
from discord.ext.commands import bot_has_permissions, has_permissions, guild_only
from lifesaver.bot import Cog, command, Context
from lifesaver.bot.storage import AsyncJSONStorage

from dog.converters import EmojiStealer


class Utility(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.afk_persistent = AsyncJSONStorage('afk.json', loop=bot.loop)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        mentioned_afk = [user for user in message.mentions if user.id in self.afk_persistent]
        mentioned_self = any(user == message.author for user in message.mentions)

        if not mentioned_afk or mentioned_self:
            return

        if len(mentioned_afk) == 1:
            reason = self.afk_persistent[mentioned_afk[0].id] or 'No reason provided.'
            notice = f'{message.author.mention}: {mentioned_afk[0]} is AFK and cannot respond at this time. ({reason})'
        else:
            users = ', '.join(str(user) for user in mentioned_afk)
            notice = f'{message.author.mention}: {users} have marked themselves as AFK and cannot respond at this time.'

        try:
            await message.channel.send(notice)
        except discord.Forbidden:
            try:
                await message.author.send(notice)
            except discord.Forbidden:
                pass

    @command()
    async def afk(self, ctx: Context, *, reason=None):
        """Marks yourself as AFK."""
        await self.afk_persistent.put(ctx.author.id, reason)
        await ctx.ok()

    @command()
    async def back(self, ctx: Context):
        """Returns from AFK status."""
        if ctx.author.id not in self.afk_persistent:
            await ctx.send("You aren't AFK!")
        else:
            await self.afk_persistent.delete(ctx.author.id)
            await ctx.ok()

    @command()
    @guild_only()
    @bot_has_permissions(manage_emojis=True, read_message_history=True)
    @has_permissions(manage_emojis=True)
    async def steal_emoji(self, ctx: Context, emoji: EmojiStealer, *, name=None):
        """Steals an emoji."""
        # the converter can return none when cancelled.
        if not emoji:
            return

        emoji_url = f'https://cdn.discordapp.com/emojis/{emoji.id}.png'

        if not emoji.name and not name:
            await ctx.send('No name was provided nor found.')
            return

        name = emoji.name or name.strip(':')
        msg = await ctx.send('Downloading...')

        try:
            async with ctx.bot.session.get(emoji_url) as resp:
                data = await resp.read()
                emoji = await ctx.guild.create_custom_emoji(name=name, image=data)

                try:
                    await msg.edit(content=str(emoji))
                    await msg.add_reaction(emoji)
                except discord.HTTPException:
                    await ctx.ok()
        except aiohttp.ClientError:
            await msg.edit(content='Failed to download the emoji.')
        except discord.HTTPException as exc:
            await msg.edit(content=f'Failed to upload the emoji: {exc}')


def setup(bot):
    bot.add_cog(Utility(bot))
