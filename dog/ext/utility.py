import random
import re

import aiohttp
import discord
import lifesaver
from discord.ext import commands
from lifesaver.utils import history_reducer

from dog.converters import EmojiStealer, UserID

EMOJI_NAME_REGEX = re.compile(r'<a?(:\w{2,32}:)\d{15,}>')


class Utility(lifesaver.Cog):
    @lifesaver.command(aliases=['ginv', 'invite'])
    async def inv(self, ctx: lifesaver.Context, *ids: UserID):
        """Generates bot invites."""
        if not ids:
            ids = (self.bot.user.id,)

        urls = '\n'.join(f'<{discord.utils.oauth_url(bot_id)}>' for bot_id in ids)
        await ctx.send(urls)

    @lifesaver.command(aliases=['shiba', 'dog'], typing=True)
    async def shibe(self, ctx: lifesaver.Context):
        """Sends a random shibe picture."""
        try:
            async with self.session.get('http://shibe.online/api/shibes?count=1&urls=true') as resp:
                data = await resp.json()

            if ctx.can_send_embeds:
                embed = discord.Embed()
                embed.set_image(url=data[0])
                await ctx.send(embed=embed)
            else:
                await ctx.send(data[0])
        except aiohttp.ClientError:
            await ctx.send('Failed to grab a shibe. \N{DOG FACE}')

    @lifesaver.command(aliases=['choose'])
    async def pick(self, ctx: lifesaver.Context, *choices: commands.clean_content):
        """Pick from a list of choices."""
        if not choices:
            await ctx.send('Send some choices.')
            return

        if len(set(choices)) == 1:
            await ctx.send('Invalid choices.')
            return

        result = random.choice(choices)
        await ctx.send(result)

    @lifesaver.command(aliases=['en'])
    @commands.guild_only()
    @commands.bot_has_permissions(read_message_history=True)
    async def emojinames(self, ctx: lifesaver.Context):
        """Shows the names of recent custom emoji used.

        Useful for mobile users.
        """

        def reducer(message):
            return EMOJI_NAME_REGEX.findall(message.content)

        emoji_names = await history_reducer(ctx, reducer, ignore_duplicates=True, limit=50)

        if not emoji_names:
            await ctx.send('No recently used custom emoji were found.')
        else:
            formatted = ', '.join(f'`{name}`' for name in emoji_names)
            await ctx.send(formatted)

    @lifesaver.command(aliases=['se'])
    @commands.guild_only()
    @commands.bot_has_permissions(manage_emojis=True, read_message_history=True)
    @commands.has_permissions(manage_emojis=True)
    async def steal_emoji(self, ctx: lifesaver.Context, emoji: EmojiStealer, name=None):
        """Steals an emoji."""
        # the converter can return none when cancelled.
        if not emoji:
            return

        extension = 'gif' if emoji.animated else 'png'
        emoji_url = f'https://cdn.discordapp.com/emojis/{emoji.id}.{extension}'

        if not emoji.name and not name:
            await ctx.send('The name of the emoji could not be resolved. Please specify one.')
            return

        name = emoji.name or name.strip(':')
        msg = await ctx.send(ctx.emoji('loading'))

        try:
            async with self.session.get(emoji_url, raise_for_status=True) as resp:
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
