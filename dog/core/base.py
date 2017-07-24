import datetime
import importlib
import os
import logging

import sys

import aiohttp
import aioredis
import asyncpg
import discord
from discord.ext import commands

from dog.core.context import DogbotContext
from dog.core.helpformatter import DogbotHelpFormatter

logger = logging.getLogger(__name__)


class BotBase(commands.bot.BotBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, formatter=DogbotHelpFormatter())

        # configuration dict
        self.cfg = kwargs.get('cfg', [])

        # aiohttp session used for fetching data
        self.session = aiohttp.ClientSession(loop=self.loop)

        # boot time (for uptime)
        self.boot_time = datetime.datetime.utcnow()

        # aioredis connection
        redis_coroutine = aioredis.create_redis(
            (self.cfg['db']['redis'], 6379), loop=self.loop)
        self.redis = self.loop.run_until_complete(redis_coroutine)

        # asyncpg
        pg = self.cfg['db']['postgres']
        self.database = pg['database']
        self.pgpool = self.loop.run_until_complete(asyncpg.create_pool(**pg))

        # load core extensions
        self.load_exts_recursively('dog/core/ext', 'Core recursive load')

    def load_exts_recursively(self, directory: str, prefix: str = 'Recursive load'):
        """ Loads extensions from a directory recursively. """

        # filter out files that we don't need
        def ext_filter(f):
            return f not in ('__init__.py', '__pycache__', '.DS_Store') and not f.endswith('.pyc')

        exts = []

        # walk the ext directory to find extensions
        for path, _, files in os.walk(directory):
            # replace the base path/like/this to path.like.this, and add the filename at the end, but without the .py
            exts += [path.replace('/', '.').replace('\\', '.') + '.' + file.replace('.py', '')
                     for file in filter(ext_filter, files)]

        logger.debug('Extensions to load: %s', exts)

        for ext in exts:
            # check if it has setup, to avoid loading non-extensions
            module = importlib.import_module(ext)
            if hasattr(module, 'setup'):
                logger.info('%s: %s', prefix, ext)
                self.load_extension(ext)
            else:
                logger.debug('Skipping %s, doesn\'t seem to be an extension.', ext)

        # keep track of a list of extensions to load
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

    async def post_to_webhook(self, content=None, *, embed: discord.Embed=None):
        """ Posts to the configured health webhook.

        If a health webhook is not configured, then Dogbot does nothing.
        """

        webhook_url = self.cfg['monitoring'].get('health_webhook', None)

        if not webhook_url:
            logger.debug('Ignoring post_to_webhook, no health_webhook! content=%s, embed=%s', content, embed)
            return

        if self.session.closed:
            logger.warning('Cannot post to webhook -- it\'s closed! Bailing.')
            return

        await self.session.post(webhook_url, json={'content': content, 'embeds': [embed.to_dict()]})

    async def on_message(self, msg):
        # do not process messages from other bots
        if msg.author.bot:
            return

        # wait until ready before processing any messages
        await self.wait_until_ready()

        ctx = await self.get_context(msg, cls=DogbotContext)
        await self.invoke(ctx)

    async def on_shard_ready(self, shard_id):
        embed = discord.Embed(title=f'Shard #{shard_id} is ready.', color=discord.Color.green())
        await self.post_to_webhook(embed=embed)

    async def on_resumed(self):
        embed = discord.Embed(title='Resumed', description='The bot has resumed its connection to Discord.',
                              color=discord.Color.orange())
        await self.post_to_webhook(embed=embed)

    async def on_ready(self):
        print('Bot is ready!')
        print('[User]', self.user)
        print('[ID]  ', self.user.id)

        ready_embed = discord.Embed(title='Bot is ready!', description='The bot has connected to Discord.',
                                    color=discord.Color.green())
        await self.post_to_webhook(embed=ready_embed)

