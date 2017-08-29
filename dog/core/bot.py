"""
The core Dogbot bot.
"""

import asyncio
import logging
import traceback

import discord
from discord.ext import commands
from ruamel.yaml import YAML

from dog.core.base import BotBase

from . import errors

logger = logging.getLogger(__name__)


class DogBot(BotBase, discord.AutoShardedClient):
    """
    The main DogBot bot. It is automatically sharded. All parameters are passed
    to the constructor of :class:`discord.commands.AutoShardedBot`.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, command_prefix=self.prefix, **kwargs)

        # list of extensions to reload (this means that new extensions are not picked up)
        # this is here so we can d?reload even if an syntax error occurs and it won't be present
        # in self.extensions
        self._exts_to_load = list(self.extensions.keys()).copy()

        # custom prefix cache
        self.prefix_cache = {}

    @property
    def is_private(self) -> bool:
        """

        Returns: Whether this bot is considered "public".

        """
        return 'private' in self.cfg['bot'] and self.cfg['bot']['private']

    def tick(self, tick_type: str, *, raw: bool = False, guild: discord.Guild = None) -> str:
        """
        Returns a custom tick emoji.

        Args:
            tick_type: The tick type to return. Either "green" or "red".
            raw: Specifies whether the returned tick shouldn't be in emoji message formatting form.
            guild: Specifies the guild that this reaction will be used in. Used in checking if we can actually use the
                   ticks. If not, we return the unicode alternatives instead.

        Returns: The tick.
        """
        raw_tick = '\U00002705' if type == 'green' else '\U0000274c'

        # use raw ticks if we can't use external emoji, or we want to
        if guild and not guild.me.guild_permissions.external_emojis:
            return raw_tick

        try:
            # fetch tick from config
            custom_tick = self.cfg['bot']['emoji'][tick_type + '_tick']
            return custom_tick if raw else f'<:{custom_tick}>'
        except KeyError:
            return raw_tick

    @property
    def green_tick(self):
        """
        Returns: The green tick emoji.
        """
        return self.tick('green')

    @property
    def red_tick(self):
        """
        Returns: The red tick emoji.
        """
        return self.tick('red')

    async def is_global_banned(self, user: discord.User) -> bool:
        key = f'cache:globalbans:{user.id}'

        if await self.redis.exists(key):
            # use the cached value instead
            return (await self.redis.get(key)).decode() == 'banned'

        async with self.pgpool.acquire() as conn:
            # grab the record from postgres, if any
            banned = (await conn.fetchrow('SELECT * FROM globalbans WHERE user_id = $1', user.id)) is not None

            # cache the banned value for 2 hours
            await self.redis.set(key, 'banned' if banned else 'not banned', expire=7200)

            # return whether banned or not
            return banned

    async def on_message(self, msg):
        await self.redis.incr('stats:messages')

        if not msg.author.bot and await self.is_global_banned(msg.author):
            return

        await super().on_message(msg)

    async def get_prefixes(self, guild: discord.Guild) -> 'List[str]':
        """ Returns the supplementary prefixes for a guild. """
        if not guild:
            return []

        if self.prefix_cache.get(guild.id):
            return self.prefix_cache[guild.id]

        async with self.pgpool.acquire() as conn:
            prefixes = await conn.fetch('SELECT prefix FROM prefixes WHERE guild_id = $1', guild.id)
            prefix_strings = list(map(lambda r: r['prefix'], prefixes))
            if prefixes and not self.prefix_cache.get(guild.id):
                self.prefix_cache[guild.id] = prefix_strings
            return [] if not prefixes else prefix_strings

    def _get_lang_data(self, lang):
        with open(f'./resources/lang/{lang}.yml') as f:
            return YAML(typ='safe').load(f)

    def _access_dot(self, dct, dot):
        cur = dct
        for part in dot.split('.'):
            cur = cur[part]
        return cur

    def lang(self, key: str, lang: str='en-US'):
        fallback_data = self._get_lang_data('en-US')
        lang_data = self._get_lang_data(lang)

        try:
            return self._access_dot(lang_data, key)
        except KeyError:
            # default to en-US
            try:
                return self._access_dot(fallback_data, key)
            except KeyError:
                # uhhh
                return key

    async def prefix(self, bot, message: discord.Message):
        """ Returns prefixes for a message. """
        mention = [self.user.mention + ' ', f'<@!{self.user.id}> ']
        additional_prefixes = await self.get_prefixes(message.guild)
        return self.cfg['bot']['prefixes'] + mention + additional_prefixes

    async def close(self):
        # close stuff
        logger.info('close() called, cleaning up...')
        self.redis.close()
        await self.pgpool.close()
        await self.session.close()

        await super().close()

    async def command_is_disabled(self, guild: discord.Guild, command_name: str):
        """ Returns whether a command is disabled in a guild. """
        return await self.redis.exists(f'disabled:{guild.id}:{command_name}')

    async def disable_command(self, guild: discord.Guild, command_name: str):
        """ Disables a command in a guild. """
        logger.debug('Disabling %s in %d.', command_name, guild.id)
        await self.redis.set(f'disabled:{guild.id}:{command_name}', 'on')

    async def enable_command(self, guild: discord.Guild, command_name: str):
        """ Enables a command in a guild. """
        logger.debug('Enabling %s in %d.', command_name, guild.id)
        await self.redis.delete(f'disabled:{guild.id}:{command_name}')

    def has_prefix(self, text: str):
        """
        Checks if text starts with a bot prefix.

        .. NOTE::

            This does not rely on `discord.commands.ext.Bot.command_prefix`,
            but rather the list of prefixes present in `dog_config`.
        """
        return any(text.startswith(p) for p in self.cfg['bot']['prefixes'])

    async def send_modlog(self, guild: discord.Guild, *args, **kwargs):
        """
        Sends a message to the #mod-log channel of a guild.

        If there is no #mod-log channel, no message is sent. All parameters are
        passed to `send()`.
        """
        try:
            key = 'modlog_channel_id'
            manual_id = int(await self.config_get(guild, key))
            manual_mod_log = discord.utils.get(guild.text_channels, id=manual_id)
        except:
            manual_mod_log = None

        mod_log = manual_mod_log or discord.utils.get(guild.text_channels, name='mod-log')

        # don't post to mod-log, couldn't find the channel
        if mod_log is None:
            return

        try:
            await self.redis.incr('stats:modlog:sends')
            return await mod_log.send(*args, **kwargs)
        except discord.Forbidden:
            # couldn't post to modlog
            logger.warning('Couldn\'t post to modlog for guild %d. No permissions.', guild.id)
            pass

    async def set_playing_statuses(self):
        short_prefix = min(self.cfg['bot']['prefixes'], key=len)
        for shard in self.shards.values():
            game = discord.Game(name=f'{short_prefix}help | shard {shard.id}')
            await shard.ws.change_presence(game=game)

    async def on_ready(self):
        await super().on_ready()

        await self.set_playing_statuses()

    async def config_get(self, guild: discord.Guild, name: str):
        """
        Returns configuration data for a guild.
        """
        return (await self.redis.get(f'{guild.id}:{name}')).decode()

    async def config_is_set(self, guild: discord.Guild, name: str) -> bool:
        """
        Returns whether a configuration key for a guild is set or not.

        .. NOTE::

            This does not look at the value of a configuration key; it just
            checks if it exists. In Dogbot, a configuration key existing
            signifies that it is set.
        """
        return await self.redis.exists(f'{guild.id}:{name}')

    async def handle_forbidden(self, ctx):
        if not ctx.guild.me:
            return

        if not ctx.guild.me.permissions_in(ctx.channel).send_messages and ctx.command:
            await ctx.message.author.send(await ctx._('misc.cant_respond'))

    async def on_command(self, ctx):
        author = ctx.message.author
        checks = [c.__qualname__.split('.')[0] for c in ctx.command.checks]
        location = '[DM] ' if isinstance(ctx.channel, discord.DMChannel) else '[Guild] '
        logger.info('%sCommand invocation by %s (%d) "%s" checks=%s', location, author, author.id, ctx.message.content,
                    ','.join(checks) or '(none)')

    async def on_command_error(self, ctx, ex):
        if getattr(ex, 'should_suppress', False):
            logger.debug('Suppressing exception: %s', ex)
            return

        if ctx.command:
            see_help = await ctx._('err.see_help', prefix=ctx.prefix, cmd=ctx.command.qualified_name)

        if isinstance(ex, commands.errors.BadArgument):
            message = str(ex)
            if not message.endswith('.'):
                message = message + '.'
            await ctx.send(await ctx._('err.bad_arg', msg=message, see_help=see_help))
        elif isinstance(ex, commands.errors.MissingRequiredArgument):
            await ctx.send(await ctx._('err.uh_oh', ex=ex, see_help=see_help))
        elif isinstance(ex, commands.NoPrivateMessage):
            await ctx.send(await ctx._('err.not_in_dm'))
        elif isinstance(ex, errors.InsufficientPermissions):
            await ctx.send(ex)
        elif isinstance(ex, commands.errors.DisabledCommand):
            await ctx.send(await ctx._('err.globally_disabled'))
        elif isinstance(ex, asyncio.TimeoutError):
            await ctx.send(await ctx._('err.timeout'))
        elif isinstance(ex, commands.errors.CommandInvokeError):
            if isinstance(ex.original, discord.Forbidden):
                if ctx.command.name == 'help':
                    # can't dm that person :(
                    try:
                        await ctx.send(await ctx._('err.dms_disabled', mention=ctx.author.mention))
                    except discord.Forbidden:
                        pass
                    return
                return await self.handle_forbidden(ctx)

            # get the traceback
            tb = ''.join(traceback.format_exception(type(ex.original), ex.original, ex.original.__traceback__))

            # form a good human-readable message
            header = f'Command error: {type(ex.original).__name__}: {ex.original}'
            message = header + '\n' + str(tb)

            self.dispatch('uncaught_command_invoke_error', ex.original, (message, tb, ctx))
            logger.error(message)
