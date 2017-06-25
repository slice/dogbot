from enum import Enum


class CensorType(Enum):
    """ Signifies types of censorship. """
    INVITES = 1
    VIDEOSITES = 2
    ZALGO = 3
    MEDIALINKS = 4
    EXECUTABLELINKS = 5


class PunishmentType(Enum):
    """ Signifies types of punishments. """
    BAN = 1
    KICK = 2
