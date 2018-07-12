import logging

import aiohttp
import asyncio
import discord
from lifesaver.bot import Bot
from lifesaver.bot.storage import AsyncJSONStorage
from quart.logging import create_serving_logger
from quart.serving import Server

from dog.guild_config import GuildConfigManager
from dog.web.server import app as webapp

log = logging.getLogger(__name__)


class Dogbot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.load_all()
        self.blacklisted_storage = AsyncJSONStorage('blacklisted_users.json', loop=self.loop)
        self.guild_configs = GuildConfigManager(self)

        webapp.bot = self
        webapp.secret_key = self.config.web['secret_key']
        self.boot_server()

    def dispatch(self, event_name, *args, **kwargs):
        """Modified version of the vanilla dispatch to fit disabled_cogs."""
        discord.Client.dispatch(self, event_name, *args, **kwargs)

        ev = 'on_' + event_name
        guild = None

        # yup, this can't go wrong at all
        # extract the guild from A.guild or A if it's already a guild, with A
        # being the first arg
        first_arg = args[0] if args else None
        if hasattr(first_arg, 'guild') and isinstance(first_arg.guild, discord.Guild):
            guild = first_arg.guild
        elif isinstance(first_arg, discord.Guild):
            guild = first_arg

        for event in self.extra_events.get(ev, []):
            # if we have a guild and the event (method) qualified name has a .
            # (which means we are inside of a cog), split the qualified name
            # to grab the cog name then check the configuration to avoid
            # dispatching if required
            ev_name = event.__qualname__
            if guild and '.' in ev_name:
                cog_name, method_name = ev_name.split('.')
                if self.cog_is_disabled(guild, cog_name):
                    # log.debug('Dropping dispatch of %s to %s in %d -- cog disabled.', ev, ev_name, guild.id)
                    continue

            coro = self._run_event(event, event_name, *args, **kwargs)
            asyncio.ensure_future(coro, loop=self.loop)

    def cog_is_disabled(self, guild: discord.Guild, cog_name: str) -> bool:
        config = self.guild_configs.get(guild)
        if config:
            disabled_cogs = config.get('disabled_cogs', [])
            return cog_name in disabled_cogs
        else:
            return False

    async def can_run(self, ctx, **kwargs):
        cog_name = type(ctx.command.instance).__name__
        if ctx.guild and self.cog_is_disabled(ctx.guild, cog_name):
            return False

        return await super().can_run(ctx, **kwargs)

    async def close(self):
        log.info('bot is exiting')
        await self.session.close()
        await super().close()

    def boot_server(self):
        self.loop.create_task(self.loop.create_server(
            lambda: Server(webapp, self.loop, create_serving_logger(), "%(h)s %(r)s %(s)s %(b)s %(D)s",
                           keep_alive_timeout=5),
            host='0.0.0.0', port=8993, ssl=None
        ))

    def is_blacklisted(self, user: discord.User) -> bool:
        return user.id in self.blacklisted_storage

    async def on_message(self, message: discord.Message):
        if self.is_blacklisted(message.author):
            return
        await super().on_message(message)
