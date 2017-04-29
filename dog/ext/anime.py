"""
Contains commands that relate to finding and showing anime.
"""

import html
import logging

import discord
from discord.ext import commands

from dog import Cog
from dog.anime import anime_search, Anime
from dog.core import utils

import dog_config as cfg

logger = logging.getLogger(__name__)


class Anime(Cog):
    def _make_anime_embed(self, anime: Anime) -> discord.Embed:
        embed = discord.Embed(title=anime.title)
        not_airing = anime.end_date == '0000-00-00' or anime.status != 'Finished Airing'
        embed.add_field(name='Score', value=anime.score)
        embed.add_field(name='Episodes', value=anime.episodes)
        embed.add_field(name='Status', value=anime.status)
        if not_airing:
            embed.add_field(name='Start date', value=anime.start_date)
        else:
            aired_value = f'{anime.start_date} - {anime.end_date}'
            if anime.start_date == anime.end_date:
                aired_value = anime.start_date + ' (one day)'
            embed.add_field(name='Aired', value=aired_value)
        synopsis = html.unescape(anime.synopsis).replace('<br />', '\n')[:2500]
        embed.add_field(name='Synopsis', value=utils.truncate(synopsis, 1000), inline=False)
        embed.set_thumbnail(url=anime.image)
        return embed

    @commands.command()
    async def anime(self, ctx, *, query: str):
        """ Searches for anime on MyAnimeList. """
        async with ctx.channel.typing():
            results = (await anime_search(self.bot.session, query))
            if results is None:
                await ctx.send('\N{PENSIVE FACE} Found nothing.')
                return
            results = results[:10]

        if len(results) > 1:
            choice = await self.bot.pick_from_list(ctx, results[:20])
            if choice is None:
                return
            await ctx.send(embed=self._make_anime_embed(choice))
        else:
            await ctx.send(embed=self._make_anime_embed(results[0]))


def setup(bot):
    if not hasattr(cfg, 'myanimelist'):
        logger.warning('No "myanimelist" attribute on config, not adding Anime cog.')
        return
    bot.add_cog(Anime(bot))
