"""
Contains fun commands that don't serve any purpose!
"""

import logging
from collections import namedtuple
from io import BytesIO
from typing import Any, Dict

import aiohttp
import discord
import random
from discord.ext import commands
from PIL import Image, ImageEnhance
from wand import image as wndimg
from wand.color import Color

from dog import Cog
from dog.core import checks, utils

SHIBE_ENDPOINT = 'http://shibe.online/api/shibes?count=1&urls=true'
DOGFACTS_ENDPOINT = 'https://dog-api.kinduff.com/api/facts'
GOOGLE_COMPLETE = 'https://www.google.com/complete/search'

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


async def urban(session: aiohttp.ClientSession, word: str) -> 'Union[UrbanDefinition, None]':
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

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def forbidden(self, ctx, who: discord.Member):
        """ At last! I am free to think the forbidden thoughts. """
        with ctx.typing():
            try:
                avatar_url = who.avatar_url_as(format='png')

                # grab the avatar data, the forbidden image, the avatar image, and create a canvas
                avatar_data = await _get_bytesio(self.bot.session, avatar_url)
                forbid = wndimg.Image(filename='resources/forbidden_thoughts.png')
                avatar = wndimg.Image(file=avatar_data)
                canvas = wndimg.Image(width=forbid.width, height=forbid.height)

                # canvas should be png
                canvas.format = 'png'

                # resize the avatar to an appropriate size
                avatar.resize(580, 580)

                # composite the avatar on the bottom, then the forbidden image on top
                canvas.composite(avatar, 980, 480)
                canvas.composite(forbid, 0, 0)

                # create a bytesio to save it to
                with BytesIO() as bio:
                    # save
                    canvas.save(file=bio)
                    bio.seek(0)

                    # send it
                    await ctx.send(file=discord.File(bio, f'forbidden-{who.id}.png'))

                # close everything
                avatar_data.close()
                forbid.close()
                avatar.close()
                canvas.close()
            except:
                await ctx.send('Something went wrong making the image. Sorry!')

    @commands.command()
    @commands.guild_only()
    @checks.config_is_set('woof_command_enabled')
    async def woof(self, ctx):
        """ A sample, secret command. """
        await ctx.send('Woof!')

    @commands.command()
    async def complete(self, ctx, *, text: str):
        """ Pushes text through Google search's autocomplete. """
        async with ctx.channel.typing():
            payload = {
                'q': text,
                'client': 'hp',
                'hl': 'en',
                'gs_rn': 64,
                'gs_ri': 'hp',
                'cp': 5,
                'gs_id': 'w',
                'xhr': 't'
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Geck'
                              'o) Chrome/58.0.3029.96 Safari/537.36'
            }
            try:
                async with self.bot.session.get(GOOGLE_COMPLETE, headers=headers,
                                                params=payload) as resp:
                    try:
                        result = random.choice((await resp.json())[1])[0]
                        await ctx.send(utils.strip_tags(result))
                    except IndexError:
                        await ctx.send('No results.')
            except aiohttp.ClientError:
                await ctx.send('Something went wrong, try again.')

    @commands.command()
    @commands.is_owner()
    async def say(self, ctx, *, text: str):
        """ Makes the bot say something. """
        await ctx.send(text)

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
    async def shibe(self, ctx):
        """
        Posts a random Shiba Inu picture.

        The pictures are from shibe.online.
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
        """ Applies some wacky effects to your avatar. """
        if not who:
            who = ctx.message.author
        logger.info('wacky: get: %s', who.avatar_url)

        async with ctx.channel.typing():
            avatar_url = who.avatar_url_as(format='png')
            with await _get_bytesio(self.bot.session, avatar_url) as avatar_data:
                try:
                    im = Image.open(avatar_data)
                except:
                    await ctx.send('I couldn\'t load that person\'s avatar.')
                    return im.close()

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
        """ Returns a random dog-related fact. """
        await ctx.send(random.choice(self.dogfacts))


def setup(bot):
    bot.add_cog(Fun(bot))
