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

    @classmethod
    async def recipe(cls, ctx, recipe):
        # type
        async with ctx.typing():
            # construct Meme class with some additional options if needed
            meme = cls(recipe['image'], ctx, **recipe.get('additional', {}))

            # cache images
            for image, size in recipe.get('cache', []):
                await meme.cache(image, size)

            # execute steps
            for step in recipe['steps']:
                if 'place' in step:
                    meme.paste(step['place'][0], step['place'][1])
                elif 'text' in step:
                    logger.info(step.get('max_width', 10e9))
                    meme.text(
                        step['text'], step['x'], step['y'],
                        step.get('max_width', 10e9), step.get('fill', (0, 0, 0))
                    )

            # render up
            await meme.render(recipe['render_as'])

            # clean
            meme.cleanup()

    async def cache(self, url, size=None):
        # already in cache?
        if url in self.image_cache:
            return self

        # download image
        image = self.image_cache[url] = await download_image(self.ctx.bot.session, url)

        # fit if a size was provided
        if size:
            self.image_cache[url] = ImageOps.fit(image, size, Image.BICUBIC)

        return self

    def paste(self, src, coords):
        # paste from cache
        if isinstance(src, str):
            self.source.paste(self.image_cache[src], coords, self.image_cache[src])
        else:
            # paste some image
            self.source.paste(src, coords, src)
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

    @commands.command()
    async def b(self, ctx, *, text: commands.clean_content):
        """ 🅱🅱🅱🅱🅱🅱🅱 """
        text = ' '.join('\U0001f171' + w[1:] for w in text.split(' '))
        await ctx.send(text.replace('b', '\U0001f171'))

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def mistake(self, ctx, image_source: converters.Image):
        """ For really big mistakes. """
        await Meme.recipe(ctx, {
            'image': 'resources/memes/mistake.png',
            'render_as': 'mistake.png',
            'cache': [ (image_source, (250, 250)) ],
            'steps': [
                { 'place': (image_source, (239, 241)) }
            ]
        })

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

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def youvs(self, ctx, a: converters.Image, b: converters.Image):
        """ You vs. the guy she tells you not to worry about """
        await Meme.recipe(ctx, {
            'image': 'resources/memes/you_vs.png',
            'render_as': 'youvs.png',
            'cache': [ (a, (330, 375)), (b, (327, 377)) ],
            'steps': [
                { 'place': (a, (22, 162)) },
                { 'place': (b, (365, 161)) }
            ]
        })

    @commands.command(aliases=['ph'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pornhub(self, ctx, image: converters.Image, *, title):
        """ Lewd. """
        await Meme.recipe(ctx, {
            'image': 'resources/memes/ph.png',
            'render_as': 'ph.png',
            'additional': {
                'font_file': 'resources/font/SourceSansPro-Bold.ttf'
            },
            'cache': [ (image, (1781, 1000)) ],
            'steps': [
                { 'place': (image, (47, 245)) },
                { 'text': title, 'x': 70, 'y': 1270, 'fill': (255, 255, 255) }
            ]
        })

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def drake(self, ctx, yay: converters.Image, nay: converters.Image):
        """ Yay or nay? """
        await Meme.recipe(ctx, {
            'image': 'resources/memes/drake.png',
            'render_as': 'drake.png',
            'cache': [ (yay, (256, 250)), (nay, (261, 254)) ],
            'steps': [
                { 'place': (yay, (242, 257)) },
                { 'place': (nay, (241, 0)) }
            ]
        })

    @commands.command(aliases=['www'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def whowouldwin(self, ctx, left: converters.Image, left_text, right: converters.Image, right_text):
        """ Who would win? """
        await Meme.recipe(ctx, {
            'image': 'resources/memes/whowouldwin.png',
            'render_as': 'whowouldwin.png',
            'cache': [
                (left, (312, 277)),
                (right, (350, 250))
            ],
            'steps': [
                { 'place': (left, (24, 200)) },
                { 'place': (right, (434, 210)) },
                { 'text': left_text, 'x': 17, 'y': 100, 'max_width': 380 },
                { 'text': right_text, 'x': 440, 'y': 112, 'max_width': 340 }
            ]
        })

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def youcantjust(self, ctx, *, text: commands.clean_content):
        """ You can't just... """
        await Meme.recipe(ctx, {
            'image': 'resources/memes/you_cant_just.png',
            'render_as': 'you_cant_just.png',
            'steps': [
                { 'text': f'"you can\'t just {text}"', 'x': 23, 'y': 12, 'max_width': 499 }
            ]
        })

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def whodidthis(self, ctx, *, image: converters.Image):
        """ Who did this? """
        await Meme.recipe(ctx, {
            'image': 'resources/memes/whodidthis.png',
            'render_as': 'whodidthis.png',
            'cache': [ (image, (717, 406)) ],
            'steps': [
                { 'place': (image, (0, 158)) }
            ]
        })

    @commands.command(aliases=['handicap'], )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def handicapped(self, ctx, image_source: converters.Image, *, text: commands.clean_content):
        """ Sir, this spot is for the handicapped only!... """
        await Meme.recipe(ctx, {
            'image': 'resources/memes/handicap.png',
            'render_as': 'handicapped.png',
            'cache': [ (image_source, (80, 80)) ],
            'steps': [
                { 'text': text, 'x': 270, 'y': 310, 'max_width': 270 },
                { 'place': (image_source, (373, 151)) },
                { 'place': (image_source, (302, 408)) },
                { 'place': (image_source, (357, 690)) }
            ]
        })

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def floor(self, ctx, image_source: converters.Image, *, text: commands.clean_content):
        """
        The floor is...

        Generates a "the floor is" type meme. The image source is composited
        on top of the jumper's face. The remaining text is used to render a caption.
        """
        await Meme.recipe(ctx, {
            'image': 'resources/memes/floor.png',
            'render_as': 'floor.png',
            'cache': [ (image_source, (100, 100)) ],
            'steps': [
                { 'text': text, 'x': 25, 'y': 25, 'max_width': 1100 },
                { 'place': (image_source, (783, 229)) },
                { 'place': (image_source, (211, 199)) }
            ]
        })

    @commands.command()
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

    @commands.command()
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
