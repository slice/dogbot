import aiohttp
import discord
from lifesaver.bot import Bot
from lifesaver.bot.storage import AsyncJSONStorage
from dog.web.server import app as webapp
from ruamel.yaml import YAML

from quart.serving import Server
from quart.logging import create_serving_logger


class GuildConfigManager:
    def __init__(self, bot):
        self.bot = bot
        self.yaml = YAML(typ='safe')
        self.persistent = AsyncJSONStorage('guild_configs.json', loop=bot.loop)

    def _id(self, obj):
        if isinstance(obj, discord.Guild):
            return str(obj.id)
        return str(obj)

    def can_edit(self, user: discord.User, guild) -> bool:
        # owners can always see the guild's configuration
        if guild.owner == user:
            return True

        config = self.get(guild)
        # no config, so only the owner is let in
        if config is None:
            return False

        editors = config.get('editors', [])
        if isinstance(editors, list):
            return str(user) in editors or user.id in editors
        elif isinstance(editors, int):
            return user.id == editors
        else:
            return False

    async def write(self, guild, config: str):
        await self.persistent.put(self._id(guild), config)

    def get(self, guild):
        config = self.persistent.get(self._id(guild))
        if config is None:
            return None
        return self.yaml.load(config)

    def __getitem__(self, guild):
        config = self.get(self._id(guild))
        if not config:
            raise KeyError(self._id(guild))
        return config


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
            lambda: Server(webapp, self.loop, create_serving_logger(), "%(h)s %(r)s %(s)s %(b)s %(D)s", keep_alive_timeout=5),
            host='0.0.0.0', port=8993, ssl=None
        ))

    def is_blacklisted(self, user: discord.User) -> bool:
        return user.id in self.blacklisted_storage

    async def on_message(self, message: discord.Message):
        if self.is_blacklisted(message.author):
            return
        await super().on_message(message)
