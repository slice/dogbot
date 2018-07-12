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
        self.parsed_cache = {}

    def _id(self, obj) -> str:
        """Resolves an object into a key for guild_configs.json."""
        if isinstance(obj, discord.Guild):
            return str(obj.id)  # unwrap ID from guild object
        return str(obj)  # just the ID was passed, probably.

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

        # special exception:
        #
        # if there is no configuration present for this guild, let in people
        # who can ban along with the owner.
        member = guild.get_member(user.id)
        if member is not None:
            can_ban = member.guild_permissions.ban_members
            if config is None and can_ban:
                return True

        # no config, so only the owner is let in
        if config is None:
            return False

        editors = config.get('editors', [])
        if isinstance(editors, list):  # list of ids
            return str(user) in editors or user.id in editors
        elif isinstance(editors, int):  # a single id
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
            # return the configuration as-is, without parsing
            return config

        # use the parsed version if applicable
        if config in self.parsed_cache:
            return self.parsed_cache[config]

        try:
            result = self.yaml.load(config)
            self.parsed_cache[config] = result  # cache
            return result
        except YAMLError:
            log.warning('Invalid YAML config (%s): %s', self._id(guild), config)
            return None

    def __getitem__(self, guild):
        config = self.get(self._id(guild))
        if not config:
            raise KeyError(self._id(guild))
        return config
