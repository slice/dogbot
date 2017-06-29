from collections import namedtuple

import asyncio
import discord
import re

import logging
from discord.ext import commands

from dog import Cog

logger = logging.getLogger(__name__)
emoji_re = re.compile(r'<:([^ ]+):(\d+)>')


class CustomEmoji(namedtuple('CustomEmoji', 'name id')):
    def __str__(self):
        return f'`:{self.name}:`'

    def __repr__(self):
        return f'<CustomEmoji name={self.name} id={self.id}>'


class Steal(Cog):
    def get_nitro_emoji_guild(self, guilds: 'List[discord.Guild]') -> discord.Guild:
        return discord.utils.find(lambda g: len(g.members) == 1, guilds)

    async def get_recently_used_emotes(self, channel: discord.TextChannel, *, amount=50) -> 'List[CustomEmoji]':
        emotes = []
        async for msg in channel.history(limit=amount):
            matches = emoji_re.findall(msg.content)
            if not matches or msg.author == self.bot.user:
                continue
            emotes += [CustomEmoji(*match) for match in matches]
        return list(set(emotes))

    @commands.group(aliases=['stealemoji', 'se'], invoke_without_command=True)
    async def stealemote(self, ctx):
        """ Steals a recently used custom emoji. """
        recently_used = await self.get_recently_used_emotes(ctx.channel)
        if not recently_used:
            return await ctx.send('No custom emoji were found in the last 50 messages.')

        if len(recently_used) > 1:
            to_steal = await ctx.pick_from_list(recently_used, delete_after_choice=True)
        else:
            to_steal = recently_used[0]

        logger.debug('Stealing emoji: %s', to_steal)

        progress = await ctx.send(f'Stealing `:{to_steal.name}:`...')
        reason = 'Stolen from {}'.format(ctx.guild.name)

        guild = self.get_nitro_emoji_guild(ctx.bot.guilds)
        logger.debug('Emoji guild: name=%s id=%d', guild.name, guild.id)

        async with ctx.bot.session.get(f'https://cdn.discordapp.com/emojis/{to_steal.id}.png') as resp:
            png_data = await resp.read()
            await guild.create_custom_emoji(name=to_steal.name, image=png_data, reason=reason)

        await progress.edit(content='Successfully stolen!')

    @stealemote.command(name='stolen')
    async def stealemote_stolen(self, ctx):
        """ Shows stolen emotes. """
        stolen = list(map(str, self.get_nitro_emoji_guild(ctx.bot.guilds).emojis))
        if not stolen:
            return await ctx.send('I have stolen no emotes thus far.')
        await ctx.send(f'Successfully stolen **{len(stolen)}** emotes: ' + ', '.join(stolen))


def setup(bot):
    bot.add_cog(Steal(bot))
