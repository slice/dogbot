import html
import discord
from dog import Cog, util
from dog.anime import anime_search
from discord.ext import commands

class Anime(Cog):
    def _make_anime_embed(self, anime):
        print(anime)
        embed = discord.Embed(title=anime.title)
        not_airing = anime.end_date == '0000-00-00' or anime.status != 'Finished Airing'
        embed.add_field(name='Score', value=anime.score)
        embed.add_field(name='Episodes', value=anime.episodes)
        embed.add_field(name='Status', value=anime.status)
        if not_airing:
            embed.add_field(name='Start date', value=anime.start_date)
        else:
            embed.add_field(name='Aired', value=f'{anime.start_date} - {anime.end_date}')
        synopsis = html.unescape(anime.synopsis).replace('<br />', '\n')[:2500]
        embed.add_field(name='Synopsis', value=util.truncate(synopsis, 1000), inline=False)
        return embed

    @commands.command()
    async def anime(self, ctx, *, query: str):
        """ Searches for anime on MyAnimeList. """
        results = (await anime_search(query))[:20]

        if len(results) > 1:
            choices = '\n'.join(f'{idx + 1}) {an.title}' for idx, an in enumerate(results))
            await ctx.send('Too many results! Pick one:\n\n' + choices)
            choice = 0

            while True:
                msg = await self.bot.wait_for_response(ctx)
                try:
                    choice = int(msg.content)
                    break
                except ValueError:
                    await ctx.send('Invalid choice. Try again.')
            await ctx.send(embed=self._make_anime_embed(results[choice - 1]))
        else:
            await ctx.send(embed=self._make_anime_embed(results[0]))

def setup(bot):
    bot.add_cog(Anime(bot))
