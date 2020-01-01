__all__ = ["GatekeeperException", "Report", "Bounce", "Ban", "create_embed"]

import datetime

import discord
from lifesaver.utils import human_delta


class GatekeeperException(RuntimeError):
    """An exception thrown during Gatekeeper processes."""


class CheckFailure(GatekeeperException):
    """An exception thrown due to a check failing to pass."""

    #: The name of the check that failed to pass.
    check_name = None

    #: The check function that failed to pass.
    check = None


class Report(GatekeeperException):
    """A Gatekeeper exception that immediately halts all processing and sends
    the specified text to the broadcasting channel.
    """


class Bounce(CheckFailure):
    """A Gatekeeper exception that will prevent a user from joining a guild when raised."""


class Ban(CheckFailure):
    """A Gatekeeper exception that will ban a user from the guild when raised."""


def create_embed(
    member: discord.Member, *, color: discord.Color, title: str, reason: str
) -> discord.Embed:
    """Create a Gatekeeper bounce or ban embed."""
    embed = discord.Embed(color=color, title=title, description=reason)
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_thumbnail(url=member.avatar_url)
    embed.add_field(
        name="Account Creation",
        value=f"{human_delta(member.created_at)} ago\n{member.created_at}",
    )
    return embed
