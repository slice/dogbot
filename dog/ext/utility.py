import aiohttp
import discord
from discord.ext.commands import bot_has_permissions, has_permissions, guild_only
from lifesaver.bot import Cog, command, Context

from dog.converters import EmojiStealer


class Utility(Cog):
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
