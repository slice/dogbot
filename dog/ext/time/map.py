import datetime
from collections import defaultdict
from io import BytesIO
from math import ceil, floor
from pathlib import Path

import aiohttp
import discord
import pytz
from PIL import Image, ImageFont, ImageDraw

from dog.ext.time.drawing import draw_text_cropped


class Map:
    def __init__(self, *, session: aiohttp.ClientSession, twelve_hour: bool = False, loop):
        self.font = ImageFont.truetype('assets/SourceSansPro-Semibold.otf', size=64)
        self.tag_font = ImageFont.truetype('assets/SourceSansPro-Black.otf', size=14)

        self.session = session
        self.twelve_hour = twelve_hour
        self.loop = loop
        self.image = None
        self.timezones = defaultdict(list)

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
        def target():
            board = Image.new('RGBA', (size, size), background)
            avatar = Image.open(fp=BytesIO(avatar_bytes)).convert('RGBA').resize((size, size), resample=Image.LANCZOS)
            board.paste(avatar, (0, 0), mask=avatar)
            self.image.paste(board, box=box, mask=board)

        avatar_url = member.avatar_url_as(static_format='png', size=size)
        async with self.session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()
            await self.loop.run_in_executor(None, target)

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

        # width: for every 3 chunks, introduce a new column
        num_columns = ceil(len(time_chunks) / chunks_per_column)
        image_width = int(max(num_columns * chunk_width, chunk_width)) + image_padding

        # height: at most 3 chunks down
        image_height = int(min(chunk_height * len(time_chunks), chunk_height * chunks_per_column)) + image_padding

        self.image = Image.new('RGBA', (image_width, image_height), background_color)
        faceplate = Image.new('RGBA', self.image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(self.image)
        draw_faceplate = ImageDraw.Draw(faceplate)

        font_height_offset = 20
        font_width_offset = 5
        avatar_size = 64

        for (time, members) in self.timezones.items():
            offset = time_chunks.index(time)

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

            members_y_top = y_top + header_size[1]
            avatar_width_total = avatar_size + (chunk_padding // 2)  # some margin
            avatars_per_row = floor(chunk_width / avatar_width_total)
            nametag_size = 15

            for n, member in enumerate(members):
                x = x_top + (avatar_width_total * (n % avatars_per_row))
                y = members_y_top + (avatar_width_total * (n // avatars_per_row))
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

        self.image.paste(faceplate, (0, 0), mask=faceplate)

        del draw_faceplate
        del draw
