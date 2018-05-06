import random
import re

import aiohttp
import discord
from discord.ext import commands
from discord.ext.commands import bot_has_permissions, guild_only, has_permissions
from lifesaver.bot import Cog, Context, command
from lifesaver.utils import history_reducer

from dog.converters import EmojiStealer, UserIDs

EMOJI_NAME_REGEX = re.compile(r'<a?(:.+:)\d+>')


class Utility(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.session = aiohttp.ClientSession(loop=bot.loop)

    def __unload(self):
        self.session.close()

    @command(aliases=['ginv', 'invite'])
    async def inv(self, ctx: Context, *ids: UserIDs):
        """Generates bot invites."""
        if not ids:
            ids = (self.bot.user.id,)

        urls = '\n'.join(f'<{discord.utils.oauth_url(bot_id)}>' for bot_id in ids)
        await ctx.send(urls)

    @command(aliases=['shiba', 'dog'], typing=True)
    async def shibe(self, ctx: Context):
        """Sends a random shibe picture."""
        try:
            async with self.session.get('http://shibe.online/api/shibes?count=1&urls=true') as resp:
                data = await resp.json()
                await ctx.send(data[0])
        except aiohttp.ClientError:
            await ctx.send('Failed to grab a shibe. \N{DOG FACE}')

    @command(aliases=['choose'])
    async def pick(self, ctx: Context, *choices: commands.clean_content):
        """Pick from a list of choices."""
        if not choices:
            await ctx.send('Send some choices.')
            return

        if len(set(choices)) == 1:
            await ctx.send('Invalid choices.')
            return

        result = random.choice(choices)
        await ctx.send(result)

    @command()
    @guild_only()
    @bot_has_permissions(read_message_history=True)
    async def emojinames(self, ctx: Context):
        """
        Shows the names of recent custom emoji used.

        Useful for mobile users, who can't see the names of custom emoji.
        """

        def reducer(message):
            return EMOJI_NAME_REGEX.findall(message.content)

        emoji_names = await history_reducer(ctx, reducer, ignore_duplicates=True, limit=50)

        if not emoji_names:
            await ctx.send('No recently used custom emoji were found.')
        else:
            formatted = ', '.join(f'`{name}`' for name in emoji_names)
            await ctx.send(formatted)

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
