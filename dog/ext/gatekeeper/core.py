class GatekeeperException(RuntimeError):
    pass


class Report(GatekeeperException):
    """An exception that immediately sends text to the broadcasting channel."""


class Block(GatekeeperException):
    """An exception that blocks a user from joining a guild."""
