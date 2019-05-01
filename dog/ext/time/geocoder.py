import asyncio
import functools

from geopy import GoogleV3

from dog.bot import Dogbot


class Geocoder:
    def __init__(self, *, bot: Dogbot, loop: asyncio.AbstractEventLoop):
        self.client = GoogleV3(api_key=bot.config.api_keys.google_maps)
        self.bot = bot
        self.loop = loop

    async def geocode(self, *args, **kwargs):
        func = functools.partial(self.client.geocode, *args, **kwargs)
        return await self.loop.run_in_executor(None, func)

    async def timezone(self, *args, **kwargs):
        func = functools.partial(self.client.timezone, *args, **kwargs)
        return await self.loop.run_in_executor(None, func)
