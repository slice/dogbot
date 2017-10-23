import logging

from aioredis import Redis
from asyncpg.pool import Pool
from aiohttp import ClientSession


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

    pgpool: Pool = _mirror('pgpool')
    redis: Redis = _mirror('redis')
    session: ClientSession = _mirror('session')
