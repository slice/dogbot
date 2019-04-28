import asyncio
import logging

import aiohttp
import discord
import hypercorn
import lifesaver
from hypercorn.asyncio.run import Server
from lifesaver.bot.storage import AsyncJSONStorage

from dog.web.server import app as webapp
from .guild_config import GuildConfigManager
from .help import HelpCommand

log = logging.getLogger(__name__)


async def _boot_hypercorn(app, config, *, loop):
    """Manually creates a Hypercorn server.

    We don't use Hypercorn's functions for server creation because it involves
    modifying the loop in undesirable ways. It also silently devours all
    KeyboardInterrupt exceptions.
    """
    socket = config.create_sockets()
    server = await loop.create_server(
        lambda: Server(app, loop, config),
        backlog=config.backlog,
        sock=socket.insecure_sockets[0],
    )
    return server


class Dogbot(lifesaver.Bot):
    def __init__(self, cfg, **kwargs):
        super().__init__(
            cfg, help_command=HelpCommand(dm_help=cfg.dm_help), **kwargs)

        self.session = aiohttp.ClientSession(loop=self.loop)
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
        self.http_server = await _boot_hypercorn(self.webapp, self.http_server_config, loop=self.loop)
        log.debug('created server: %r', self.http_server)

    def is_blacklisted(self, user: discord.User) -> bool:
        return user.id in self.blacklisted_storage

    async def on_message(self, message: discord.Message):
        await self.wait_until_ready()

        if self.is_blacklisted(message.author):
            return

        await super().on_message(message)
