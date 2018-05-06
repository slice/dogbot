import logging

import discord
from lifesaver.bot.storage import AsyncJSONStorage
from ruamel.yaml import YAML, YAMLError

log = logging.getLogger(__name__)


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
        # resolve passed ids
        if isinstance(guild, int):
            guild = self.bot.get_guild(guild)
            if not guild:
                return False

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

    def get(self, guild, *, yaml: bool = False):
        config = self.persistent.get(self._id(guild))
        if config is None:
            return None
        if yaml:
            return config

        try:
            return self.yaml.load(config)
        except YAMLError:
            log.warning('Invalid YAML config: %s', config)
            return None

    def __getitem__(self, guild):
        config = self.get(self._id(guild))
        if not config:
            raise KeyError(self._id(guild))
        return config
