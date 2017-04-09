import logging
import aiohttp
import discord
import tempfile
from PIL import Image, ImageEnhance
from discord.ext import commands
from dog import Cog
from io import BytesIO

SHIBE_ENDPOINT = 'http://shibe.online/api/shibes?count=1&urls=true&httpsUrls=true'
DOGFACTS_ENDPOINT = 'https://dog-api.kinduff.com/api/facts'

logger = logging.getLogger(__name__)

async def _get(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return response

async def _get_bytesio(url):
    # can't use _get for some reason
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return BytesIO(await resp.read())

async def _get_json(url):
    resp = await _get(url)
    return await resp.json()


class Fun(Cog):
    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def shibe(self, ctx):
        """
        Woof!

        Grabs a random Shiba Inu picture from shibe.online.
        """
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
        facts = await _get_json(DOGFACTS_ENDPOINT)
        if not facts['success']:
            await ctx.send('I couldn\'t contact the Dog Facts API.')
            return
        await ctx.send(facts['facts'][0])


def setup(bot):
    bot.add_cog(Fun(bot))
