"""
Contains fun commands that don't serve any purpose!
"""

import logging
from collections import namedtuple

import aiohttp
import discord
import random

from discord.ext import commands

from dog import Cog
from dog.core import checks, utils

logger = logging.getLogger(__name__)


UrbanDefinition = namedtuple('UrbanDefinition', [
    'word', 'definition', 'thumbs_up', 'thumbs_down', 'example',
    'permalink', 'author', 'defid', 'current_vote'
])


async def urban(session, word):
    """ Queries UrbanDictionary for a definition. """
    UD_ENDPOINT = 'http://api.urbandictionary.com/v0/define?term={}'
    async with session.get(UD_ENDPOINT.format(utils.urlescape(word))) as resp:
        json = await resp.json()
        if json['result_type'] == 'no_results':
            return None
        result = json['list'][0]
        return UrbanDefinition(**result)


def make_urban_embed(d: UrbanDefinition) -> discord.Embed:
    """ Makes a ``discord.Embed`` from an ``UrbanDefinition``. """
    embed = discord.Embed(title=d.word, description=utils.truncate(d.definition, 2048))
    if d.example:
        embed.add_field(name='Example', value=utils.truncate(d.example, 1024), inline=False)
    embed.add_field(name='\N{THUMBS UP SIGN}', value=utils.commas(d.thumbs_up))
    embed.add_field(name='\N{THUMBS DOWN SIGN}', value=utils.commas(d.thumbs_down))
    return embed


class Fun(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        with open('resources/dogfacts.txt') as dogfacts:
            self.dogfacts = [fact.strip() for fact in dogfacts.readlines()]

    @commands.command(hidden=True)
    @commands.cooldown(1, 1, commands.BucketType.channel)
    async def clap(self, ctx, *, text: commands.clean_content):
        """👏MAKES👏TEXT👏LOOK👏LIKE👏THIS👏"""
        clap = '\N{CLAPPING HANDS SIGN}'
        await ctx.send(clap + text.replace(' ', clap) + clap)

    @commands.command(hidden=True)
    async def mock(self, ctx, *, text: commands.clean_content):
        """Mocks."""
        ev = random.randint(2, 4)
        result = [character.upper() if not text.index(character) % ev == 0 else character.lower() for character in text]
        await ctx.send(''.join(result))

    @commands.command()
    @checks.is_moderator()
    async def say(self, ctx, channel: discord.TextChannel, *, text: commands.clean_content):
        """
        Makes the bot say something in a certain channel.

        Mentions will be scrubbed, meaning that they will be converted to plain text
        to avoid abuse.

        Dogbot Moderator is required to do this.
        """
        try:
            await channel.send(text)
        except discord.Forbidden:
            await ctx.send(f'I can\'t speak in {channel.mention}.')
        except discord.HTTPException:
            await ctx.send(f'Your message is too long! 2,000 characters maximum.')

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def urban(self, ctx, *, word: str):
        """ Finds UrbanDictionary definitions. """
        async with ctx.channel.typing():
            try:
                result = await urban(self.bot.session, word)
            except aiohttp.ClientError:
                return await ctx.send('Failed to look up that word!')
            if not result:
                return await ctx.send('No results!')
            await ctx.send(embed=make_urban_embed(result))

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def dogfact(self, ctx):
        """ Returns a random dog-related fact. """
        await ctx.send(random.choice(self.dogfacts))


def setup(bot):
    bot.add_cog(Fun(bot))
