__all__ = ['Map']

import datetime
import logging
from collections import defaultdict
from io import BytesIO
from math import ceil, floor
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import discord
import pytz
from PIL import Image, ImageDraw, ImageFont

from dog.ext.time.drawing import draw_text_cropped

log = logging.getLogger(__name__)


class Map:
    def __init__(self, *, session: aiohttp.ClientSession, twelve_hour: bool = False, loop):
        self.font = ImageFont.truetype('assets/SourceSansPro-Semibold.otf', size=64)
        self.tag_font = ImageFont.truetype('assets/SourceSansPro-Black.otf', size=14)

        self.session = session
        self.twelve_hour = twelve_hour
        self.loop = loop
        self.image = None
        self.timezones = defaultdict(list)

        self.cache = Path.cwd() / 'avatar_cache'
        self.cache.mkdir(exist_ok=True)

    @property
    def format(self):
        if self.twelve_hour:
            return '%I:%M %p'
        else:
            return '%H:%M'

    def close(self):
        self.image.close()

    def add_member(self, member: discord.Member, timezone: str):
        """Add a member to the chart."""
        now = datetime.datetime.now(pytz.timezone(timezone))
        formatted = now.strftime(self.format)
        self.timezones[formatted].append(member)

    async def draw_member(self, member: discord.Member, box, *, size: int, background):
        def target(avatar_bytes):
            # overlay transparent avatars with a subtle background
            board = Image.new('RGBA', (size, size), background)
            avatar = Image.open(fp=BytesIO(avatar_bytes))\
                .convert('RGBA')\
                .resize((size, size), resample=Image.LANCZOS)
            board.paste(avatar, (0, 0), mask=avatar)
            self.image.paste(board, box=box, mask=board)

        avatar_url = str(member.avatar_url_as(format='png', size=size))
        filename = urlparse(avatar_url).path.split('/')[-1]
        cached_file = self.cache / filename

        if cached_file.is_file():
            log.debug('Using cached file for %d: %s', member.id, cached_file)
            await self.loop.run_in_executor(None, target, cached_file.read_bytes())
        else:
            log.debug('Fetching uncached file for %d: %s', member.id, cached_file)
            async with self.session.get(avatar_url) as resp:
                avatar_bytes = await resp.read()
                cached_file.write_bytes(avatar_bytes)
                await self.loop.run_in_executor(None, target, avatar_bytes)

    async def render(self):
        def save():
            buffer = BytesIO()
            self.image.save(buffer, format='png')
            buffer.seek(0)  # go back to beginning
            return buffer

        buffer = await self.loop.run_in_executor(None, save)
        return buffer

    async def draw(self):
        time_chunks = list(self.timezones.keys())
        background_color = (49, 52, 58)

        image_padding = 50
        chunk_padding = 20
        chunk_width = 500
        chunk_height = 300
        chunks_per_column = 3

        # the number of columns: for every 3 chunks, introduce a new column
        num_columns = ceil(len(time_chunks) / chunks_per_column)

        # the width of the image: clamp down to 1 chunk wide
        image_width = int(max(num_columns * chunk_width, chunk_width)) + image_padding

        # the height of the image: at most, 3 chunks down vertically
        image_height = int(
            min(
                # if the number of time chunks is less than 3 chunks, we can
                # make the image smaller
                chunk_height * len(time_chunks),

                # max out at 3 chunks per column
                chunk_height * chunks_per_column
            )
        ) + image_padding

        self.image = Image.new('RGBA', (image_width, image_height), background_color)

        # a faceplate must be used in order to draw nametags because ImageDraw
        # can't draw transparent stuff on top of the existing pixels. so, we
        # create a new image which is exactly the size of the original image,
        # draw on that, then overlay it exactly on top later
        faceplate = Image.new('RGBA', self.image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(self.image)
        draw_faceplate = ImageDraw.Draw(faceplate)

        font_height_offset = 20
        font_width_offset = 5
        avatar_size = 64

        for (time, members) in self.timezones.items():
            offset = time_chunks.index(time)

            # calculate the x and y coordinates of this chunk based on the
            # offset of this timezone's presence in the list
            x_top = chunk_width * (offset // 3) + chunk_padding + image_padding
            y_top = chunk_height * (offset % 3) + chunk_padding + image_padding

            # draw the header of the chunk
            draw.text(
                (
                    x_top - font_width_offset,
                    y_top - font_height_offset,
                ),
                time,
                fill=(255, 255, 255, 255),
                font=self.font
            )
            header_size = draw.textsize(time, font=self.font)

            # the y coordinate for the avatar listing
            members_y_top = y_top + header_size[1]

            # the total size of an avatar with padding
            avatar_size_total = avatar_size + (chunk_padding // 2)  # some margin

            # how many avatars can fit into each row before having to wrap?
            avatars_per_row = floor(chunk_width / avatar_size_total)
            safe_width = avatars_per_row * avatar_size_total

            # the height of the nametag displayed inside of avatars
            nametag_size = 15

            # maximum number of rows of avatars that can fit in each chunk --
            # calculated by seeing how many rows of avatars can fit in the total
            # chunk height, along with the header
            max_rows = floor((chunk_height - header_size[1]) / (avatar_size_total))

            for n, member in enumerate(members):
                row = n // avatars_per_row
                col = n % avatars_per_row

                # start collapsing on the last row, not the row after the last
                # row.
                if row + 1 >= max_rows:
                    # we have run out of rows! we now have to overlap avatars
                    # horizontally on the last row.

                    # calculate the amount of remaining avatars that still have
                    # to be rendered on the last row
                    leading_rows = max_rows - 1
                    leading_avatars = leading_rows * avatars_per_row
                    remaining = len(members[leading_avatars:])

                    # calculate the overlap between each avatar necessary so
                    # they can all fit into a single row. clamp down to the
                    # normal size increments (avatar size and some margins)
                    even_overlap = min(safe_width // remaining, avatar_size_total)

                    x = x_top + (even_overlap * (n - leading_avatars))
                    y = members_y_top + (avatar_size_total * leading_rows)
                else:
                    x = x_top + (avatar_size_total * col)
                    y = members_y_top + (avatar_size_total * row)

                await self.draw_member(member, (x, y), size=avatar_size, background=(45, 47, 52))

                text = member.name

                draw_faceplate.rectangle(
                    (
                        x, y + avatar_size - nametag_size - 1,
                        x + avatar_size - 1, y + avatar_size - 1,
                    ),
                    fill=(0, 0, 0, 100)
                )

                draw_text_cropped(
                    draw_faceplate,
                    (x, y + avatar_size - nametag_size),
                    (0, 0, avatar_size, nametag_size),
                    text,
                    fill=(255, 255, 255),
                    font=self.tag_font
                )

        # apply the transparent faceplate on top of the image
        self.image.paste(faceplate, (0, 0), mask=faceplate)

        del draw_faceplate
        del draw
