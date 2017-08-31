import logging


class Cog:
    """ The Cog baseclass that all cogs should inherit from. """
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('cog.' + type(self).__name__.lower())
