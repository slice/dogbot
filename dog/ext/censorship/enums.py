from enum import Enum

from dog.core.utils import EnumConverter


class CensorType(EnumConverter, Enum):
    """Signifies types of censorship."""
    INVITES = 1
    VIDEOSITES = 2
    ZALGO = 3
    MEDIALINKS = 4
    EXECUTABLELINKS = 5
    CAPS = 6
    CRASH_TEXT = 7


class PunishmentType(EnumConverter, Enum):
    """Signifies types of punishments."""
    BAN = 1
    KICK = 2
