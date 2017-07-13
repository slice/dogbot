import logging
import re
from collections import namedtuple
from io import BytesIO
from zipfile import ZipFile

import discord
import time
from discord.ext import commands
from PIL import Image

from dog import Cog
from dog.core import converters
from dog.core.utils import get_bytesio

logger = logging.getLogger(__name__)
emoji_re = re.compile(r'<:([^ ]+):(\d+)>')


class CustomEmoji(namedtuple('CustomEmoji', 'name id')):
    def __str__(self):
        return f'`:{self.name}:`'

    def __repr__(self):
        return f'<CustomEmoji name={self.name} id={self.id}>'


class Steal(Cog):
    def get_nitro_emoji_guild(self, guilds: 'List[discord.Guild]') -> discord.Guild:
        return discord.utils.find(lambda g: len(g.members) == 1, guilds)

    async def get_recently_used_emotes(self, channel: discord.TextChannel, *, amount=50) -> 'List[CustomEmoji]':
        emotes = []
        async for msg in channel.history(limit=amount):
            matches = emoji_re.findall(msg.content)
            if not matches or msg.author == self.bot.user:
                continue
            emotes += [CustomEmoji(*match) for match in matches]
        return list(set(emotes))

    async def rip_emojis(self, ctx, source):
        # calculate how many rows we need
        rows = round(len(source["emojis"]) / 10)

        # create the preview image and zip file
        im = Image.new('RGBA', (32 * 10, 32 * rows))
        zip = ZipFile(f'{source["id"]}.zip', 'w')

        for index, emoji in enumerate(source["emojis"]):
            # fetch the emoji
            emoji_bio = await get_bytesio(ctx.bot.session, f'https://cdn.discordapp.com/emojis/{emoji.id}.png')

            # write it to the zip
            zip.writestr(f'{emoji.name}-{emoji.id}.png', emoji_bio.read())
            emoji_bio.seek(0)

            # open the emoji
            emoji_image = Image.open(emoji_bio).convert('RGBA').resize((32, 32), Image.BICUBIC)

            # composite the emoji into the preview image
            row = int(index / 10) * 32
            col = (index % 10) * 32
            im.paste(emoji_image, (col, row))

            # close
            emoji_bio.close()
            emoji_image.close()

        # send the preview image
        with BytesIO() as bio:
            await ctx.bot.loop.run_in_executor(None, im.save, bio, 'png')
            bio.seek(0)
            await ctx.send(file=discord.File(bio, f'emoji-{source["id"]}.png'))

        # close zip and send it
        zip.close()
        await ctx.send(file=discord.File(f'{source["id"]}.zip'))

    @commands.group(invoke_without_command=True)
    async def rip(self, ctx, where: converters.Guild):
        """ Rips all of the emoji from a guild. """
        await self.rip_emojis(ctx, {'id': where.id, 'emojis': where.emojis})

    @rip.command(name='colate')
    async def rip_colate(self, ctx, *keywords):
        """ Rips emoji with keywords. """
        emoji = [em for em in ctx.bot.emojis if any(kw in em.name for kw in keywords)]
        logger.debug('Colating %d emoji.', len(emoji))
        await self.rip_emojis(ctx, {'id': f'colated-{time.time()}', 'emojis': emoji})

    @commands.group(aliases=['stealemoji', 'se'], invoke_without_command=True)
    async def stealemote(self, ctx):
        """ Steals a recently used custom emoji. """
        recently_used = await self.get_recently_used_emotes(ctx.channel)
        if not recently_used:
            return await ctx.send('No custom emoji were found in the last 50 messages.')

        if len(recently_used) > 1:
            to_steal = await ctx.pick_from_list(recently_used, delete_after_choice=True)
        else:
            to_steal = recently_used[0]

        logger.debug('Stealing emoji: %s', to_steal)

        progress = await ctx.send(f'Stealing `:{to_steal.name}:`...')
        reason = 'Stolen from {}'.format(ctx.guild.name)

        guild = self.get_nitro_emoji_guild(ctx.bot.guilds)
        logger.debug('Emoji guild: name=%s id=%d', guild.name, guild.id)

        async with ctx.bot.session.get(f'https://cdn.discordapp.com/emojis/{to_steal.id}.png') as resp:
            png_data = await resp.read()
            await guild.create_custom_emoji(name=to_steal.name, image=png_data, reason=reason)

        await progress.edit(content='Successfully stolen!')

    @stealemote.command(name='stolen')
    async def stealemote_stolen(self, ctx):
        """ Shows stolen emotes. """
        stolen = list(map(str, self.get_nitro_emoji_guild(ctx.bot.guilds).emojis))
        if not stolen:
            return await ctx.send('I have stolen no emotes thus far.')
        await ctx.send(f'Successfully stolen **{len(stolen)}** emotes: ' + ', '.join(stolen))


def setup(bot):
    bot.add_cog(Steal(bot))
