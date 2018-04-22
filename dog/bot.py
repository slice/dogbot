import aiohttp
import discord
from lifesaver.bot import Bot
from lifesaver.bot.storage import AsyncJSONStorage
from dog.web.server import app as webapp


class Dogbot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.load_all()
        self.blacklisted_storage = AsyncJSONStorage('blacklisted_users.json', loop=self.loop)
        webapp.bot = self
        self.loop.create_task(webapp.create_server(host='0.0.0.0', port=8993))

    def is_blacklisted(self, user: discord.User) -> bool:
        return user.id in self.blacklisted_storage

    async def on_message(self, message: discord.Message):
        if self.is_blacklisted(message.author):
            return
        await super().on_message(message)
