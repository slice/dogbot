"""
Contains fun commands that don't serve any purpose!
"""

import logging
import tempfile
from collections import namedtuple
from io import BytesIO

import aiohttp
import discord
from discord.ext import commands
from PIL import Image, ImageEnhance

from dog import Cog
from dog.core import checks, utils

SHIBE_ENDPOINT = 'http://shibe.online/api/shibes?count=1&urls=true&httpsUrls=true'
DOGFACTS_ENDPOINT = 'https://dog-api.kinduff.com/api/facts'

logger = logging.getLogger(__name__)

async def _get(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return response

async def _get_bytesio(url: str):
    # can't use _get for some reason
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return BytesIO(await resp.read())

async def _get_json(url: str):
    resp = await _get(url)
    return await resp.json()

UrbanDefinition = namedtuple('UrbanDefinition', [
    'word', 'definition', 'thumbs_up', 'thumbs_down', 'example',
    'permalink', 'author', 'defid', 'current_vote'
])

async def urban(word: str):
    UD_ENDPOINT = 'http://api.urbandictionary.com/v0/define?term={}'
    async with aiohttp.ClientSession() as session:
        async with session.get(UD_ENDPOINT.format(utils.urlescape(word))) as resp:
            json = await resp.json()
            if json['result_type'] == 'no_results':
                return None
            else:
                result = json['list'][0]
                return UrbanDefinition(**result)

class Fun(Cog):
    @commands.command()
    @commands.guild_only()
    @checks.config_is_set('woof_command_enabled')
    async def woof(self, ctx):
        """ Sample command. """
        await ctx.send('Woof!')

    def make_urban_embed(self, urban: UrbanDefinition):
        embed = discord.Embed(title=urban.word, description=urban.definition)
        embed.add_field(name='Example', value=urban.example, inline=False)
        embed.add_field(name='\N{THUMBS UP SIGN}', value=utils.commas(urban.thumbs_up))
        embed.add_field(name='\N{THUMBS DOWN SIGN}', value=utils.commas(urban.thumbs_down))
        return embed

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def urban(self, ctx, *, word: str):
        """ Finds UrbanDictionary definitions. """
        async with ctx.channel.typing():
            result = await urban(word)
            if not result:
                await ctx.send('No results!')
            else:
                await ctx.send(embed=self.make_urban_embed(result))

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def shibe(self, ctx):
        """
        Woof!

        Grabs a random Shiba Inu picture from shibe.online.
        """
        async with ctx.channel.typing():
            await ctx.send((await _get_json(SHIBE_ENDPOINT))[0])

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def wacky(self, ctx, who: discord.Member=None):
        """ Turns your avatar into... """
        if not who:
            who = ctx.message.author
        logger.info('wacky: get: %s', who.avatar_url)

        async with ctx.channel.typing():
            avatar_data = await _get_bytesio(who.avatar_url_as(format='png'))

            logger.info('wacky: enhancing...')
            im = Image.open(avatar_data)
            converter = ImageEnhance.Color(im)
            im = converter.enhance(50)

            # ugh
            _temp = next(tempfile._get_candidate_names())
            _path = f'{tempfile._get_default_tempdir()}/{_temp}'

            logger.info('wacky: saving...')
            im.save(_path, format='jpeg', quality=0)
            logger.info('wacky: sending...')
            await ctx.send(file=discord.File(_path, 'result.jpg'))

            # close images
            avatar_data.close()

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def dogfact(self, ctx):
        """ Returns a random dog fact. """
        async with ctx.channel.typing():
            facts = await _get_json(DOGFACTS_ENDPOINT)
            if not facts['success']:
                await ctx.send('I couldn\'t contact the Dog Facts API.')
                return
            await ctx.send(facts['facts'][0])


def setup(bot):
    bot.add_cog(Fun(bot))
