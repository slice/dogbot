"""
Contains fun commands that don't serve any purpose!
"""

import logging
from collections import namedtuple
from io import BytesIO
from typing import Any, Dict

import aiohttp
import discord
from discord.ext import commands
from PIL import Image, ImageEnhance

from dog import Cog
from dog.core import checks, utils

SHIBE_ENDPOINT = 'http://shibe.online/api/shibes?count=1&urls=true&httpsUrls=true'
DOGFACTS_ENDPOINT = 'https://dog-api.kinduff.com/api/facts'

logger = logging.getLogger(__name__)


async def _get(session: aiohttp.ClientSession, url: str) -> aiohttp.ClientResponse:
    async with session.get(url) as response:
        return response


async def _get_bytesio(session: aiohttp.ClientSession, url: str) -> BytesIO:
    # can't use _get for some reason
    async with session.get(url) as resp:
        return BytesIO(await resp.read())


async def _get_json(session: aiohttp.ClientSession, url: str) -> Dict[Any, Any]:
    resp = await _get(session, url)
    return await resp.json()

UrbanDefinition = namedtuple('UrbanDefinition', [
    'word', 'definition', 'thumbs_up', 'thumbs_down', 'example',
    'permalink', 'author', 'defid', 'current_vote'
])


async def urban(session: aiohttp.ClientSession, word: str) -> UrbanDefinition:
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
    embed = discord.Embed(title=d.word, description=d.definition)
    embed.add_field(name='Example', value=d.example, inline=False)
    embed.add_field(name='\N{THUMBS UP SIGN}', value=utils.commas(d.thumbs_up))
    embed.add_field(name='\N{THUMBS DOWN SIGN}', value=utils.commas(d.thumbs_down))
    return embed


class Fun(Cog):
    @commands.command()
    @commands.guild_only()
    @checks.config_is_set('woof_command_enabled')
    async def woof(self, ctx):
        """ Sample command. """
        await ctx.send('Woof!')

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def urban(self, ctx, *, word: str):
        """ Finds UrbanDictionary definitions. """
        async with ctx.channel.typing():
            result = await urban(self.bot.session, word)
            if not result:
                return await ctx.send('No results!')
            await ctx.send(embed=make_urban_embed(result))

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def shibe(self, ctx):
        """
        Woof!

        Grabs a random Shiba Inu picture from shibe.online.
        """
        async with ctx.channel.typing():
            try:
                resp = await _get_json(self.bot.session, SHIBE_ENDPOINT)
            except aiohttp.ClientError:
                return await ctx.send('\N{DISAPPOINTED FACE} Failed to contact the shibe API.')
            dog_url = resp[0]
            await ctx.send(embed=discord.Embed().set_image(url=dog_url))

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def wacky(self, ctx, who: discord.Member=None):
        """ Turns your avatar into... """
        if not who:
            who = ctx.message.author
        logger.info('wacky: get: %s', who.avatar_url)

        async with ctx.channel.typing():
            avatar_url = who.avatar_url_as(format='png')
            with await _get_bytesio(self.bot.session, avatar_url) as avatar_data:
                im = Image.open(avatar_data)
                converter = ImageEnhance.Color(im)
                im = converter.enhance(50)

                with BytesIO() as bio:
                    im.save(bio, format='jpeg', quality=0)
                    bio.seek(0)
                    await ctx.send(file=discord.File(bio, 'result.jpg'))

                im.close()

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def dogfact(self, ctx):
        """ Returns a random dog fact. """
        async with ctx.channel.typing():
            try:
                facts = await _get_json(self.bot.session, DOGFACTS_ENDPOINT)
            except aiohttp.ClientError:
                return await ctx.send('\N{DISAPPOINTED FACE} Failed to get a dog fact.')
            if not facts['success']:
                await ctx.send('I couldn\'t contact the Dog Facts API.')
                return
            await ctx.send(facts['facts'][0])


def setup(bot):
    bot.add_cog(Fun(bot))
