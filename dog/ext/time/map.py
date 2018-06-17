import datetime
import functools
from collections import defaultdict
from io import BytesIO

import aiohttp
import discord
import pytz
from PIL import Image, ImageFont

from .drawing import draw_rotated_text


class Map:
    def __init__(self, *, session: aiohttp.ClientSession, twelve_hour: bool = False, loop):
        self.font = ImageFont.truetype('assets/SourceSansPro-Bold.otf', size=35)
        self.image = Image.open('assets/timezone_map.png').convert('RGBA')
        self.session = session
        self.twelve_hour = twelve_hour
        self.loop = loop

        # defaultdict to keep track of users and their timezones.
        #
        # keys are a tuple: (time as pretty string, hour offset)
        # values are a discord.Member
        #
        # this is because users can have the same time offset, but have different
        # actual times because timezones are inconsistent. bleh.
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
        now = datetime.datetime.now(pytz.timezone(timezone))

        # calculate the hour offset, not accounting for dst
        offset = (now.utcoffset().total_seconds() - now.dst().total_seconds()) / 60 / 60
        formatted = now.strftime(self.format)

        self.timezones[(formatted, offset)].append(member)

    async def draw_member(self, member: discord.Member, x, y):
        def target():
            avatar = Image.open(fp=BytesIO(avatar_bytes)).convert('RGBA')
            self.image.paste(avatar, box=(x, y), mask=avatar)

        avatar_url = member.avatar_url_as(static_format='png', size=32)
        async with self.session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()
            await self.loop.run_in_executor(None, target)

    async def draw_rotated_text(self, *args, **kwargs):
        func = functools.partial(draw_rotated_text, *args, **kwargs)
        return await self.loop.run_in_executor(None, func)

    async def render(self):
        def save():
            buffer = BytesIO()
            self.image.save(buffer, format='png')
            buffer.seek(0)  # go back to beginning
            return buffer

        buffer = await self.loop.run_in_executor(None, save)
        return buffer

    async def draw(self):
        # keep track of how far up we are for each hour offset, so there are no
        # overlaps. (this is for each "pretty group")
        offset_positions = defaultdict(int)

        for (formatted, offset), members in self.timezones.items():
            # x position based on hour, for appropriate positioning on the map
            x = int((offset + 11) * 38.5 + 21)

            begin_y = offset_positions[str(offset)]
            y = begin_y if begin_y != 0 else 480  # start at 480 pixels down if we don't have an offset already

            for member in members:
                await self.draw_member(member, x, y)

                # move up the map (32 for avatar, 5 for some padding)
                y -= 32 + 5

            size = await self.draw_rotated_text(
                self.image, 90, (x - 7, y + 30), formatted, fill=(0, 0, 0, 255),
                font=self.font
            )

            # register our offset (size[0] is text width)
            # because it's rotated by 90 degrees, we use width instead of height
            offset_positions[str(offset)] = y - size[0] - 30
