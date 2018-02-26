from typing import Any

import discord


class Report(Exception):
    """
    An exception that immediately sends text to the broadcasting channel.
    This should only be thrown inside of a :class:`GatekeeperCheck`.
    """
    pass


class Check:
    """A Gatekeeper check."""
    key: str = None

    async def check(self, config_value: Any, member: discord.Member):
        raise NotImplementedError


class Block(Exception):
    """
    An exception that blocks a user from joining a guild.
    This should only be thrown inside of a :class:`GatekeeperCheck`.
    """
    pass
