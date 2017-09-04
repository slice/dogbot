import logging

import asyncio
from random import randrange

import aiohttp
import discord
import functools
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageOps
from discord.ext import commands
from io import BytesIO

from dog import Cog
from dog.core import converters, utils
from dog.core.utils import get_bytesio, urlescape

logger = logging.getLogger(__name__)


async def download_image(session, url):
    bio = await get_bytesio(session, url)
    im = Image.open(bio).convert('RGBA')
    bio.close()
    return im


async def export_image(ctx, image, filename):
    with BytesIO() as bio:
        # export the image
        coro = ctx.bot.loop.run_in_executor(None, functools.partial(image.save, bio, format='png'))
        await asyncio.wait([coro], loop=ctx.bot.loop, timeout=5)

        # upload
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename))


class Meme:
    def __init__(self, source, ctx, *, text_size=32, font_file=None):
        self.ctx = ctx
        self.image_cache = {}
        self.source = Image.open(source).convert('RGBA')
        self.draw = ImageDraw.Draw(self.source)
        self.font = ImageFont.truetype(font_file or 'resources/font/SourceSansPro-Regular.ttf', text_size)

    async def cache(self, url, size=None):
        # already in cache?
        if url in self.image_cache:
            return self

        # download image
        image = self.image_cache[url] = await download_image(self.ctx.bot.session, url)

        # fit if a size was provided
        if size:
            self.image_cache[url] = ImageOps.fit(image, size)

        return self

    def paste(self, src, coords):
        # paste from cache
        if isinstance(src, str):
            self.source.paste(self.image_cache[src], coords)
        else:
            # paste some image
            self.source.paste(src, coords)
        return self

    def text(self, text, x, y, width, fill=(0, 0, 0)):
        # draw some text
        utils.draw_word_wrap(self.draw, self.font, text, x, y, width, fill)
        return self

    async def render(self, filename='image.png'):
        await export_image(self.ctx, self.source, filename)
        return self

    def cleanup(self):
        for url, im in self.image_cache.items():
            logger.debug('Cleaning up after cached image %s...', url)
            im.close()
        del self.draw
        self.source.close()


class Memes(Cog):
    async def __error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            logger.exception('Memes image processing error!')
            await ctx.send('Something went wrong processing your image. Sorry about that!')
            error.should_suppress = True
        elif isinstance(error, asyncio.TimeoutError):
            await ctx.send('Your image took too long to process, so I dropped it.')
            error.should_suppress = True

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def jpeg(self, ctx, image_source: converters.Image):
        """
        Drastically lowers an image's quality.

        This command takes an image, and saves it as a JPEG with the quality of 1.
        """
        im_data = await get_bytesio(self.bot.session, image_source)

        def open():
            return Image.open(im_data).convert('RGB')
        im = await ctx.bot.loop.run_in_executor(None, open)

        with BytesIO() as output:
            await ctx.bot.loop.run_in_executor(None, functools.partial(im.save, output, format='jpeg', quality=1))
            output.seek(0)
            await ctx.send(file=discord.File(output, filename='jpeg.jpg'))

        im.close()
        im_data.close()

    @commands.command(hidden=True)
    async def b(self, ctx, *, text: commands.clean_content):
        """ 🅱🅱🅱🅱🅱🅱🅱 """
        text = ' '.join('\U0001f171' + w[1:] for w in text.split(' '))
        await ctx.send(text.replace('b', '\U0001f171'))

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def mistake(self, ctx, image_source: converters.Image):
        """ For really big mistakes. """
        async with ctx.typing():
            m = Meme('resources/memes/mistake.png', ctx)
            await m.cache(image_source, (250, 250))
            m.paste(image_source, (239, 241))
            await m.render('mistake.png')
            m.cleanup()

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def orly(self, ctx, title, guide, author, *, top_text=''):
        """ Generates O'Reilly book covers. """

        api_base = 'https://orly-appstore.herokuapp.com/generate?'

        url = (api_base +
               f'title={urlescape(title)}&top_text={urlescape(top_text)}&image_code={randrange(0, 41)}' +
               f'&theme={randrange(0, 17)}&author={urlescape(author)}&guide_text={urlescape(guide)}' +
               f'&guide_text_placement=bottom_right')

        try:
            async with ctx.typing():
                async with ctx.bot.session.get(url) as resp:
                    with BytesIO(await resp.read()) as bio:
                        await ctx.send(file=discord.File(filename='orly.png', fp=bio))
        except aiohttp.ClientError:
            await ctx.send("Couldn't contact the API.")

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def trustnobody(self, ctx, image_source: converters.Image):
        """ Trust nobody, not even yourself. """
        async with ctx.typing():
            m = Meme('resources/memes/trust_nobody.png', ctx)

            im = (await download_image(ctx.bot.session, image_source))
            im = ImageOps.fit(im, (100, 100), Image.BICUBIC)
            m.paste(im, (82, 230))
            im = im.crop((0, 0, 62, 100))
            m.paste(im, (420, 250))
            im.close()

            await m.render('trust_nobody.png')
            m.cleanup()

    @commands.command(hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def youvs(self, ctx, a: converters.Image, b: converters.Image):
        """ You vs. the guy she tells you not to worry about """
        async with ctx.typing():
            m = Meme('resources/memes/you_vs.png', ctx)
            await m.cache(a, (330, 375))
            await m.cache(b, (327, 377))
            m.paste(a, (22, 162))
            m.paste(b, (365, 161))
            await m.render('youvs.png')
            m.cleanup()

    @commands.command(hidden=True, aliases=['ph'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pornhub(self, ctx, image: converters.Image, *, title):
        """ lewd """
        async with ctx.typing():
            m = Meme('resources/memes/ph.png', ctx, text_size=45, font_file='resources/font/SourceSansPro-Bold.ttf')
            await m.cache(image, (1781, 1000))
            m.paste(image, (47, 245))
            m.text(title, 70, 1270, 10e9, (255, 255, 255)) # disable wrapping
            await m.render('ph.png')
            m.cleanup()

    @commands.command(hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def drake(self, ctx, yay: converters.Image, nay: converters.Image):
        """ yay, nay """
        async with ctx.typing():
            m = Meme('resources/memes/drake.png', ctx)
            await m.cache(yay, (256, 250))
            await m.cache(nay, (261, 254))
            m.paste(yay, (242, 257))
            m.paste(nay, (241, 0))
            await m.render('drake.png')
            m.cleanup()

    @commands.command(hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def youcantjust(self, ctx, *, text: commands.clean_content):
        """ You can't just... """
        async with ctx.typing():
            m = Meme('resources/memes/you_cant_just.png', ctx, text_size=16)
            m.text(f'"you can\'t just {text}"', 23, 12, 499)
            await m.render('youcantjust.png')
            m.cleanup()

    @commands.command(hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def whodidthis(self, ctx, *, image: converters.Image):
        """ Who did this? """
        async with ctx.typing():
            m = Meme('resources/memes/whodidthis.png', ctx)
            await m.cache(image, (717, 406))
            m.paste(image, (0, 158))
            await m.render('whodidthis.png')
            m.cleanup()

    @commands.command(aliases=['handicap'], hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def handicapped(self, ctx, image_source: converters.Image, *, text: commands.clean_content):
        """ Sir, this spot is for the handicapped only!... """
        async with ctx.typing():
            m = Meme('resources/memes/handicap.png', ctx, text_size=24)

            await m.cache(image_source, (80, 80))

            m.text(text, 270, 310, 270)
            m.paste(image_source, (373, 151))
            m.paste(image_source, (302, 408))
            m.paste(image_source, (357, 690))

            await m.render('handicapped.png')

            m.cleanup()

    @commands.command(hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def floor(self, ctx, image_source: converters.Image, *, text: commands.clean_content):
        """
        The floor is...

        Generates a "the floor is" type meme. The image source is composited
        on top of the jumper's face. The remaining text is used to render a caption.
        """

        async with ctx.typing():
            m = Meme('resources/memes/floor.png', ctx, text_size=48)

            await m.cache(image_source, (100, 100))

            m.text(text, 25, 25, 1100)
            m.paste(image_source, (783, 229))
            m.paste(image_source, (211, 199))

            await m.render('floor.png')

    @commands.command(hidden=True)
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def pixelate(self, ctx, image_source: converters.Image, size: int=15):
        """ Pixelates something. """
        if size < 5:
            await ctx.send('The minimum size is 5.')
        size = min(size, 25)
        async with ctx.typing():
            im: Image = await download_image(ctx.bot.session, image_source)
            original_size = im.size
            im = im.resize((size, size), Image.NEAREST)
            im = im.resize(original_size, Image.NEAREST)
            await export_image(ctx, im, 'pixelated.png')
            im.close()

    @commands.command(hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def wacky(self, ctx, image_source: converters.Image = None):
        """ Applies wacky effects to your avatar. """
        image_source = image_source or ctx.message.author.avatar_url_as(format='png')

        await ctx.channel.trigger_typing()
        avatar_bio = await get_bytesio(self.bot.session, image_source)

        # attempt to load the avatar
        try:
            avatar_im = Image.open(avatar_bio)
        except:
            await ctx.send('I couldn\'t load that person\'s avatar.')
            logger.exception('Wacky avatar processing error.')
            avatar_bio.close()
            return

        enhancer = ImageEnhance.Color(avatar_im)
        avatar_im = await self.bot.loop.run_in_executor(None, enhancer.enhance, 50)

        await export_image(ctx, avatar_im, 'result.png')

        avatar_bio.close()
        avatar_im.close()


def setup(bot):
    bot.add_cog(Memes(bot))
