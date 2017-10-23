import logging


def _mirror(name):
    @property
    def _mirror(self):
        return getattr(self.bot, name)
    return _mirror


class Cog:
    """The Cog baseclass that all cogs should inherit from."""
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('cog.' + type(self).__name__.lower())

    pgpool = _mirror('pgpool')
    redis = _mirror('redis')
    session = _mirror('session')
