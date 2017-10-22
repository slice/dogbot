"""
Contains fun commands that don't serve any purpose!
"""

import logging
from collections import namedtuple
from typing import Union

import aiohttp
import discord
import random
from aiohttp import ClientSession, ClientError
from discord import TextChannel, Embed
from discord.ext import commands
from discord.ext.commands import command, cooldown, clean_content, BucketType

from dog import Cog
from dog.core import utils
from dog.core.checks import is_moderator

FW_TRANSLATE = str.maketrans(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890\',.:;!?" ',
    'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ１２３４５６７８９０＇，．：；！？＂　'
)

SHIBE_ENDPOINT = 'http://shibe.online/api/shibes?count=1&urls=true'
UD_ENDPOINT = 'http://api.urbandictionary.com/v0/define?term={}'

logger = logging.getLogger(__name__)


class UrbanDefinition(namedtuple('UrbanDefinition', 'word definition thumbs_up thumbs_down example permalink author '
                                                    'defid current_vote')):
    """Represents an Urban Dictionary entry."""

    @property
    def embed(self) -> Embed:
        """Makes a :class:``discord.Embed`` from an ``UrbanDefinition``."""
        embed = Embed(title=self.word, description=utils.truncate(self.definition, 2048))
        if self.example:
            embed.add_field(name='Example', value=utils.truncate(self.example, 1024), inline=False)
        embed.add_field(name='\N{THUMBS UP SIGN}', value=utils.commas(self.thumbs_up))
        embed.add_field(name='\N{THUMBS DOWN SIGN}', value=utils.commas(self.thumbs_down))
        return embed

    @classmethod
    async def query(cls, session: ClientSession, word: str) -> Union[None, 'UrbanDefinition']:
        """Queries UrbanDictionary for a definition."""
        async with session.get(UD_ENDPOINT.format(utils.urlescape(word))) as resp:
            json = await resp.json()

            # no results :(
            if json['result_type'] == 'no_results':
                return None

            result = json['list'][0]
            return cls(**result)


class Fun(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.dogfacts = [fact.strip() for fact in open('resources/dogfacts.txt')]

    @command(hidden=True)
    @cooldown(1, 1, BucketType.channel)
    async def clap(self, ctx, *, text: commands.clean_content):
        """ 👏MAKES👏TEXT👏LOOK👏LIKE👏THIS👏 """
        clap = '\N{CLAPPING HANDS SIGN}'
        await ctx.send(clap + text.replace(' ', clap) + clap)

    @command(hidden=True)
    async def mock(self, ctx, *, text: clean_content):
        """ Mocks. """
        ev = random.randint(2, 4)
        result = [character.upper() if not text.index(character) % ev == 0 else character.lower() for character in text]
        await ctx.send(''.join(result))

    @command(hidden=True)
    async def spaced(self, ctx, *, text: clean_content):
        """ S P A C E D """
        await ctx.send(text.replace('', ' ').strip())

    @command(hidden=True, aliases=['fw'])
    async def fullwidth(self, ctx, *, text: clean_content):
        """ ＡＥＳＴＨＥＴＩＣ """
        await ctx.send(text.upper().translate(FW_TRANSLATE))

    @command()
    @is_moderator()
    async def say(self, ctx, channel: TextChannel, *, text: clean_content):
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

    @command()
    @cooldown(1, 2, BucketType.user)
    async def urban(self, ctx, *, word: str):
        """ Finds UrbanDictionary definitions. """
        async with ctx.channel.typing():
            try:
                result = await UrbanDefinition.query(self.bot.session, word)
            except ClientError:
                return await ctx.send('Failed to look up that word!')

            if not result:
                return await ctx.send('No results.')

            await ctx.send(embed=result.embed)

    @command(aliases=['shiba', 'dog'])
    @cooldown(1, 2, BucketType.user)
    async def shibe(self, ctx):
        """ Posts a random Shiba Inu picture. """
        async with ctx.typing():
            try:
                resp = await utils.get_json(ctx.bot.session, SHIBE_ENDPOINT)
            except aiohttp.ClientError:
                return await ctx.send('Failed to contact the Shibe API. Please try again later.')
            await ctx.send(embed=discord.Embed().set_image(url=resp[0]))

    @command()
    @cooldown(1, 2, BucketType.user)
    async def dogfact(self, ctx):
        """ Returns a random dog-related fact. """
        await ctx.send(random.choice(self.dogfacts))


def setup(bot):
    bot.add_cog(Fun(bot))
