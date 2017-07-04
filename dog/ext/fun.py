"""
Contains fun commands that don't serve any purpose!
"""

import asyncio
import logging
from collections import namedtuple
from io import BytesIO
from typing import Any, Dict

import aiohttp
import discord
import random
from discord.ext import commands
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
from wand import image as wndimg

from dog import Cog
from dog.core import checks, utils

SHIBE_ENDPOINT = 'http://shibe.online/api/shibes?count=1&urls=true'
GOOGLE_COMPLETE = 'https://www.google.com/complete/search'

logger = logging.getLogger(__name__)


# http://jesselegg.com/archives/2009/09/5/simple-word-wrap-algorithm-pythons-pil/
def draw_word_wrap(draw, font, text, xpos=0, ypos=0, max_width=130, fill=(0, 0, 0)):
    text_size_x, text_size_y = draw.textsize(text, font=font)
    remaining = max_width
    space_width, space_height = draw.textsize(' ', font=font)
    output_text = []
    for word in text.split(None):
        word_width, word_height = draw.textsize(word, font=font)
        if word_width + space_width > remaining:
            output_text.append(word)
            remaining = max_width - word_width
        else:
            if not output_text:
                output_text.append(word)
            else:
                output = output_text.pop()
                output += ' %s' % word
                output_text.append(output)
            remaining = remaining - (word_width + space_width)
    for text in output_text:
        draw.text((xpos, ypos), text, font=font, fill=fill)
        ypos += text_size_y


async def get_bytesio(session: aiohttp.ClientSession, url: str) -> BytesIO:
    async with session.get(url) as resp:
        return BytesIO(await resp.read())


async def get_json(session: aiohttp.ClientSession, url: str) -> Dict[Any, Any]:
    async with session.get(url) as resp:
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
    @commands.cooldown(1, 1, commands.BucketType.channel)
    async def clap(self, ctx, *, text: commands.clean_content):
        """👏MAKES👏TEXT👏LOOK👏LIKE👏THIS👏"""
        clap = '\N{CLAPPING HANDS SIGN}'
        await ctx.send(clap + text.replace(' ', clap) + clap)

    @commands.command()
    async def mock(self, ctx, *, text: commands.clean_content):
        """Mocks."""
        ev = random.randint(2, 4)
        result = [character.upper() if not text.index(character) % ev == 0 else character.lower() for character in text]
        await ctx.send(''.join(result))

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def floor(self, ctx, who: discord.Member, *, text: commands.clean_content):
        """The floor is..."""

        # open resources we need
        floor_im = Image.open('resources/floor.png')
        fnt = ImageFont.truetype('resources/font/SourceSansPro-Regular.ttf', 48)

        # download the avatar
        abio = get_bytesio(self.bot.session, who.avatar_url_as(format='png'))
        ava_im = Image.open(abio)

        # draw text
        draw = ImageDraw.Draw(floor_im)
        draw_word_wrap(draw, fnt, text, 25, 25, 1100)

        # paste avatars
        ava_im = ava_im.resize((100, 100), Image.BICUBIC)
        floor_im.paste(ava_im, (783, 229))
        floor_im.paste(ava_im, (211, 199))

        del draw

        with BytesIO() as bio:
            # process
            save = self.bot.loop.run_in_executor(None, floor_im.save, bio, 'PNG')
            await asyncio.wait([save], loop=self.bot.loop, timeout=3.5)

            # upload
            bio.seek(0)
            await ctx.send(file=discord.File(bio, filename='floor.png'))

        floor_im.close()
        ava_im.close()
        abio.close()

    @floor.error
    async def floor_errors(self, ctx, err):
        if isinstance(err, asyncio.TimeoutError):
            await ctx.send('Took too long to process the image.')
        else:
            await ctx.send('Couldn\'t process the image correctly, sorry!')

        err.should_suppress = True

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def forbidden(self, ctx, *, who: discord.Member):
        """ At last! I am free to think the forbidden thoughts. """
        with ctx.typing():
            try:
                avatar_url = who.avatar_url_as(format='png')

                # grab the avatar data, the forbidden image, the avatar image, and create a canvas
                avatar_data = await get_bytesio(self.bot.session, avatar_url)
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
    async def shibe(self, ctx):
        """
        Posts a random Shiba Inu picture.

        The pictures are from shibe.online.
        """
        async with ctx.channel.typing():
            try:
                resp = await get_json(self.bot.session, SHIBE_ENDPOINT)
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
            with await get_bytesio(self.bot.session, avatar_url) as avatar_data:
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
