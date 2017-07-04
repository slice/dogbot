import logging

import asyncio

import discord
import functools
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
from discord.ext import commands
from io import BytesIO

from dog import Cog
from dog.core import converters, utils
from dog.core.utils import get_bytesio
from wand import image as wndimg

logger = logging.getLogger(__name__)


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
    async def floor(self, ctx, image_source: converters.ImageSourceConverter, *, text: commands.clean_content):
        """The floor is..."""

        async with ctx.typing():
            # open resources we need
            floor_im = Image.open('resources/floor.png')
            fnt = ImageFont.truetype('resources/font/SourceSansPro-Regular.ttf', 48)

            # download the avatar
            abio = await get_bytesio(self.bot.session, image_source)
            ava_im = Image.open(abio)

            # draw text
            draw = ImageDraw.Draw(floor_im)
            utils.draw_word_wrap(draw, fnt, text, 25, 25, 1100)

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

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def forbidden(self, ctx, *, image_source: converters.ImageSourceConverter = None):
        """ At last! I am free to think the forbidden thoughts. """
        image_source = image_source or ctx.author.avatar_url_as(format='png')

        await ctx.channel.trigger_typing()
        avatar_data = await get_bytesio(self.bot.session, image_source)
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
            await ctx.bot.loop.run_in_executor(None, functools.partial(canvas.save, file=bio))
            bio.seek(0)

            # send it
            await ctx.send(file=discord.File(bio, f'forbidden.png'))

        # close everything
        avatar_data.close()
        forbid.close()
        avatar.close()
        canvas.close()

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def wacky(self, ctx, image_source: converters.ImageSourceConverter = None):
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

        finished_image = BytesIO()
        try:
            await self.bot.loop.run_in_executor(None, functools.partial(avatar_im.save, finished_image, format='png'))
        except:
            avatar_bio.close()
            avatar_im.close()
            finished_image.close()
            logger.exception('Wacky processing error.')
            return await ctx.send('An error has occurred processing your image.')

        finished_image.seek(0)
        await ctx.send(file=discord.File(finished_image, 'result.png'))

        avatar_bio.close()
        avatar_im.close()
        finished_image.close()


def setup(bot):
    bot.add_cog(Memes(bot))
