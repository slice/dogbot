import logging

import aiohttp
import discord
from lifesaver.bot import Bot
from lifesaver.bot.storage import AsyncJSONStorage

from dog.guild_config import GuildConfigManager
from dog.web.server import app as webapp

from quart.serving import Server
from quart.logging import create_serving_logger

log = logging.getLogger(__name__)


class Dogbot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.load_all()
        self.blacklisted_storage = AsyncJSONStorage('blacklisted_users.json', loop=self.loop)
        self.guild_configs = GuildConfigManager(self)

        webapp.bot = self
        webapp.secret_key = self.cfg.web['secret_key']
        self.boot_server()

    def boot_server(self):
        self.loop.create_task(self.loop.create_server(
            lambda: Server(webapp, self.loop, create_serving_logger(), "%(h)s %(r)s %(s)s %(b)s %(D)s",
                           keep_alive_timeout=5),
            host='0.0.0.0', port=8993, ssl=None
        ))

    def is_blacklisted(self, user: discord.User) -> bool:
        return user.id in self.blacklisted_storage

    async def on_message(self, message: discord.Message):
        if self.is_blacklisted(message.author):
            return
        await super().on_message(message)
