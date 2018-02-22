import aiohttp
import discord
from lifesaver.bot import Bot
from lifesaver.bot.storage import AsyncJSONStorage


class Dogbot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.load_all()
        self.blacklisted_storage = AsyncJSONStorage('blacklisted_users.json', loop=self.loop)

    async def on_message(self, message: discord.Message):
        if message.author.id in self.blacklisted_storage:
            return
        await super().on_message(message)
