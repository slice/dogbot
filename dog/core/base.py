import datetime
import importlib
import os
import logging

import sys

import aiohttp
import aioredis
import asyncpg
from discord.ext import commands

from dog.core.context import DogbotContext

logger = logging.getLogger(__name__)


class ReloadableBot(commands.Bot):
    """ A bot subclass that contains utility methods that aid in reloading cogs and extensions, and recursively
    loading extensions. """
    def load_exts_recursively(self, directory: str, prefix: str = 'Recursive load'):
        """ Loads extensions from a directory recursively. """
        def ext_filter(f):
            return f not in ('__init__.py', '__pycache__') and not f.endswith('.pyc')

        exts = []

        # walk the ext directory to find extensions
        for path, _, files in os.walk(directory):
            # replace the base path/like/this to path.like.this
            # add the filename at the end, but without the .py
            # filter out stuff we don't need
            exts += [path.replace('/', '.').replace('\\', '.') + '.' + file.replace('.py', '')
                     for file in filter(ext_filter, files)]

        for ext in exts:

            module = importlib.import_module(ext)
            if hasattr(module, 'setup'):
                logger.info('%s: %s', prefix, ext)
                self.load_extension(ext)
            else:
                logger.debug('Skipping %s, doesn\'t seem to be an extension.', ext)

        # update exts to load
        self._exts_to_load = list(self.extensions.keys()).copy()

    def reload_extension(self, name: str):
        """ Reloads an extension. """
        self.unload_extension(name)
        self.load_extension(name)

    def perform_full_reload(self):
        """ Fully reloads Dogbot.

        This reloads all Dogbot related modules, and all
        extensions.
        """
        logger.info('*** Performing full reload! ***')
        self.reload_all_extensions()
        self.reload_modules()

    def reload_all_extensions(self):
        """ Reloads all extensions. """
        logger.info('Reloading all %d extensions', len(self._exts_to_load))
        for name in self._exts_to_load:
            try:
                logger.info('Reloading extension: %s', name)
                self.reload_extension(name)
            except:
                logger.exception('While reloading all: Failed extension reload for %s', name)
                raise

    def reload_modules(self):
        """ Reloads all Dogbot related modules. """
        # get applicable modules to reload
        modules = {k: m for k, m in sys.modules.items() if 'dog' in k and 'ext' not in k and
                   k != 'dog'}
        for name, module in modules.items():
            logger.info('Reloading bot module: %s', name)
            importlib.reload(module)
        logger.info('Finished reloading bot modules!')


class DBBot(commands.Bot):
    """ A bot subclass that has access to Redis and Postgres. """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # hack because __init__ cannot be async
        redis_coroutine = aioredis.create_redis(
            (kwargs.pop('redis_url'), 6379), loop=self.loop)

        # aioredis connection
        self.redis = self.loop.run_until_complete(redis_coroutine)

        # asyncpg
        self.pgpool = self.loop.run_until_complete(asyncpg.create_pool(**kwargs.pop('postgresql_auth')))


class BaseBot(ReloadableBot, DBBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # aiohttp session used for fetching data
        self.session = aiohttp.ClientSession(loop=self.loop)

        # boot time (for uptime)
        self.boot_time = datetime.datetime.utcnow()

        # load core extensions
        self.load_exts_recursively('dog/core/ext', 'Core recursive load')

    async def on_message(self, msg):
        # do not process messages from other bots
        if msg.author.bot:
            return

        ctx = await self.get_context(msg, cls=DogbotContext)
        await self.invoke(ctx)

    async def on_ready(self):
        print('Bot is ready!')
        print('[User]', self.user)
        print('[ID]  ', self.user.id)


class Selfbot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(self_bot=True, *args, **kwargs)

    async def is_owner(self, user):
        return True
