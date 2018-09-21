from typing import Any, Optional

import discord


class Report(Exception):
    """
    An exception that immediately sends text to the broadcasting channel.
    This should only be thrown inside of a :class:`GatekeeperCheck`.
    """
    pass


class Check:
    """A Gatekeeper check."""
    key: Optional[str] = None

    def __init__(self, cog, member: discord.Member):
        self.cog = cog
        self.member = member

    @property
    def guild(self) -> discord.Guild:
        return self.member.guild

    async def check(self, config_value: Any):
        raise NotImplementedError


class Block(Exception):
    """
    An exception that blocks a user from joining a guild.
    This should only be thrown inside of a :class:`GatekeeperCheck`.
    """
    pass
