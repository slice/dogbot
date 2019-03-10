import logging

import aiohttp
import asyncio
import discord
import hypercorn
from hypercorn.asyncio.run import Server
from lifesaver.bot import Bot
from lifesaver.bot.storage import AsyncJSONStorage

from dog.context import Context
from dog.guild_config import GuildConfigManager
from dog.web.server import app as webapp
from dog.helpformatter import HelpFormatter

log = logging.getLogger(__name__)


async def _boot_hypercorn(app, config, *, loop):
    """Manually creates a Hypercorn server.

    Hypercorn's facilities for running a server on an already existing loop
    modify the loop in ways that make it impossible to use CTRL-C to kill the
    bot for some reason. Hypercorn does this by silently catching
    KeyboardInterrupts and setting signal handlers on the event loop, but this
    fails to work for some reason.
    """
    socket = config.create_sockets()
    server = await loop.create_server(
        lambda: Server(app, loop, config),
        backlog=config.backlog,
        sock=socket[0],
    )
    return server


class Dogbot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, context_cls=Context, formatter=HelpFormatter(), **kwargs)
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.load_all()
        self.blacklisted_storage = AsyncJSONStorage('blacklisted_users.json', loop=self.loop)
        self.guild_configs = GuildConfigManager(self)

        # webapp (quart) setup
        webapp.config.from_mapping(self.config.web['app'])
        webapp.bot = self
        self.webapp = webapp

        # http server (hypercorn) setup
        self.http_server_config = hypercorn.Config.from_mapping(self.config.web['http'])
        self.http_server = None
        self.loop.create_task(self._boot_http_server())

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
            if ev_name.count('.') == 1 and guild and '.' in ev_name:
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

        return False

    async def can_run(self, ctx, **kwargs):
        cog_name = type(ctx.command.cog).__name__
        if ctx.guild and self.cog_is_disabled(ctx.guild, cog_name):
            return False

        return await super().can_run(ctx, **kwargs)

    async def close(self):
        log.info('bot is exiting')
        await self.session.close()
        self.http_server.close()
        await self.http_server.wait_closed()
        await super().close()

    async def _boot_http_server(self):
        log.info('creating http server')
        server = await _boot_hypercorn(self.webapp, self.http_server_config, loop=self.loop)
        log.debug('created server: %r', server)

    def is_blacklisted(self, user: discord.User) -> bool:
        return user.id in self.blacklisted_storage

    async def on_message(self, message: discord.Message):
        await self.wait_until_ready()

        if self.is_blacklisted(message.author):
            return

        await super().on_message(message)
