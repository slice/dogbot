import logging

import discord
from lifesaver.bot.storage import AsyncJSONStorage
from ruamel.yaml import YAML, YAMLError

log = logging.getLogger(__name__)


def into_str_id(obj) -> str:
    """Ensures that an object is a string of an ID."""
    if isinstance(obj, discord.Guild):
        return str(obj.id)  # unwrap ID from guild object
    return str(obj)  # just the ID was passed, probably.


class GuildConfigManager:
    def __init__(self, bot):
        self.bot = bot
        self.yaml = YAML()
        self.persistent = AsyncJSONStorage('guild_configs.json', loop=bot.loop)
        self.parsed_cache = {}

    def can_edit(self, user: discord.User, guild, *, with_config=None) -> bool:
        """Return whether a user can edit a guild's config.

        This function also accepts a ``with_config`` parameter, which will be
        used instead of the guild's current config. This is useful if you want
        to test whether a certain config will lock an editor out.
        """
        if isinstance(guild, int):
            guild = self.bot.get_guild(guild)
            if not guild:
                return False

        # owners can always edit the guild's configuration
        if guild.owner == user:
            return True

        config = with_config or self.get(guild)
        member = guild.get_member(user.id)

        # special exception:
        #
        # if there is no config for this guild, let people who can ban edit the
        # config. this is useful for quicker setup.
        if config is None:
            if member is not None and member.guild_permissions.ban_members:
                return True
            return False

        editors = config.get('editors', [])

        if isinstance(editors, list):
            is_allowed = any([
                # name#discriminator in editors
                str(user) in editors,

                # user id in editors
                user.id in editors,

                # role id in editors
                member is not None and any(role.id in editors for role in member.roles),
            ])

            return is_allowed

        if isinstance(editors, int):
            return user.id == editors

        return False

    async def write(self, guild, config: str):
        await self.persistent.put(into_str_id(guild), config)

    def get(self, guild, *, yaml: bool = False):
        config = self.persistent.get(into_str_id(guild))
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
            log.warning('Invalid YAML config (%s): %s', into_str_id(guild), config)
            return None

    def __getitem__(self, guild):
        config = self.get(into_str_id(guild))
        if not config:
            raise KeyError(into_str_id(guild))
        return config
