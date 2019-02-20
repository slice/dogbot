class GatekeeperException(RuntimeError):
    """An exception thrown during Gatekeeper processes."""


class Report(GatekeeperException):
    """An exception that stops processing and sends text to the broadcasting channel."""


class Bounce(GatekeeperException):
    """An exception that prevents a user from joining a guild."""
