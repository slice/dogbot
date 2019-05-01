__all__ = ['GuildConfigManager']

import logging
from typing import Optional, Union, TypeVar

import discord
from ruamel.yaml import YAML, YAMLError
from lifesaver.bot.storage import AsyncJSONStorage

T = TypeVar('T')
GuildOrGuildID = Union[discord.Guild, int]
log = logging.getLogger(__name__)


def into_str_id(entity: Union[discord.Guild, int]) -> str:
    """Ensures that an object is a string of an ID."""
    if isinstance(entity, discord.Guild):
        return str(entity.id)
    return str(entity)


class GuildConfigManager:
    def __init__(self, bot) -> None:
        self.bot = bot
        self.yaml = YAML()
        self.persistent = AsyncJSONStorage('guild_configs.json', loop=bot.loop)
        self.parsed_cache = {}

    def resolve_guild(self, guild_or_id: GuildOrGuildID) -> Optional[discord.Guild]:
        if isinstance(guild_or_id, int):
            guild = self.bot.get_guild(guild_or_id)
            return guild
        return guild_or_id

    def can_edit(self, user: discord.User, guild: GuildOrGuildID, *, with_config: dict = None) -> bool:
        """Return whether a user can edit a guild's config.

        Parameters
        ----------
        user
            The user to check.
        guild
            A :class:`discord.Guild` object or an ID of a guild to use the
            configuration of.
        with_config
            The configuration to use instead of the guild's configuration. This
            is useful for testing whether a specific config can lock a user
            out or not.
        """
        guild = self.resolve_guild(guild)
        if not guild:
            return False

        # owners can always edit the guild's configuration
        if guild.owner == user:
            return True

        config = with_config or self.get(guild)
        member = guild.get_member(user.id)

        # if there's no config, let people who can ban members edit the config.
        # this is useful for expediting setup.
        if config is None:
            return member is not None and member.guild_permissions.ban_members

        editors = config.get('editors', [])

        # a list of "user targets" to check against for this specific user
        # (the usual code path)
        if isinstance(editors, list):
            return (
                # name#discriminator
                str(user) in editors

                # user id
                or user.id in editors

                # role id
                or (member is not None and any(role.id in editors for role in member.roles))
            )

        # a singular id
        if isinstance(editors, int):
            return user.id == editors

        return False

    async def write(self, guild: GuildOrGuildID, config: str) -> None:
        """Write the configuration of a guild.

        This will dispatch ``guild_config_edit``.

        Parameters
        ----------
        guild
            A :class:`discord.Guild` object or an ID of a guild to write the
            configuration to.
        config
            The raw configuration text in YAML.
        """
        await self.persistent.put(into_str_id(guild), config)

        guild = self.resolve_guild(guild)

        if guild is not None:
            parsed_config = self.get(guild)
            log.debug('dispatching guild_config_edit for %d (%r)', guild.id, parsed_config)
            self.bot.dispatch('guild_config_edit', guild, parsed_config)

    def get(self, guild: GuildOrGuildID, default: T = None, *, yaml: bool = False) -> Union[dict, str, T]:
        """Return the configuration of a guild.

        Parameters
        ----------
        guild
            A :class:`discord.Guild` object or an ID of a guild to fetch the
            configuration of.
        default
            The value to return if the guild provided has no configuration.
        yaml
            Return raw configuration text rather than the parsed configuration.
        """
        config = self.persistent.get(into_str_id(guild))

        if not config:  # handles both None and empty string
            return default

        # return the configuration text without parsing
        if yaml:
            return config

        # use the parsed version in cache if available
        if config in self.parsed_cache:
            return self.parsed_cache[config]

        try:
            result = self.yaml.load(config)
            self.parsed_cache[config] = result
            return result
        except YAMLError:
            log.warning('Invalid YAML config (%s): %s', into_str_id(guild), config)
            return default

    def __getitem__(self, guild: GuildOrGuildID) -> str:
        config = self.get(guild)
        if not config:
            raise KeyError(into_str_id(guild))
        return config
