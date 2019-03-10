import datetime
import random
import re
from collections import defaultdict

import aiohttp
import discord
from discord.ext import commands
from discord.ext.commands import bot_has_permissions, guild_only, has_permissions, group
from lifesaver.bot import Cog, Context, command
from lifesaver.utils import history_reducer

from dog.converters import EmojiStealer, UserIDs

EMOJI_NAME_REGEX = re.compile(r'<a?(:.+:)\d+>')


class Utility(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.gateway_lag = defaultdict(list)

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return

        config = self.bot.guild_configs.get(message.guild)
        if not config or not config.get('measure_gateway_lag', False):
            return

        # calculate gateway lag
        lag = int((datetime.datetime.utcnow() - message.created_at).total_seconds() * 1000)

        self.gateway_lag[message.channel.id].append(lag)

    @command(aliases=['ginv', 'invite'])
    async def inv(self, ctx: Context, *ids: UserIDs):
        """Generates bot invites."""
        if not ids:
            ids = (self.bot.user.id,)

        urls = '\n'.join(f'<{discord.utils.oauth_url(bot_id)}>' for bot_id in ids)
        await ctx.send(urls)

    @group(hidden=True, invoke_without_command=True)
    @guild_only()
    async def gw_lag(self, ctx: Context):
        """Views gateway lag for this channel."""
        config = ctx.bot.guild_configs.get(ctx.guild)
        if not config or not config.get('measure_gateway_lag', False):
            await ctx.send('No guild configuration was found, or gateway lag measuring was disabled.')
            return
        latencies = self.gateway_lag[ctx.channel.id]
        if not latencies:
            await ctx.send('Not enough latencies were collected.')
            return
        await ctx.send(
            '**Gateway latency report**\n\n'
            f'channel: {ctx.channel.mention} (`{ctx.channel.id}`), collected: {len(latencies):,}\n'
            f'max: `{max(latencies)}ms`, min: `{min(latencies)}ms`, avg: `{sum(latencies)/len(latencies):.2f}ms`'
        )

    @gw_lag.command(name='clear')
    @guild_only()
    @has_permissions(manage_messages=True)
    async def gw_lag_clear(self, ctx: Context):
        """Clear gathered latencies for this channel."""
        self.gateway_lag[ctx.channel.id] = []
        await ctx.ok()

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
