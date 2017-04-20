import asyncio
import aioredis
import datetime
import logging
import discord
import traceback
import raven
from discord.ext import commands
from dog import errors
from dog.utils import pretty_timedelta
import dog_config as cfg

logger = logging.getLogger(__name__)


class DogBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.boot_time = datetime.datetime.utcnow()
        _loop = asyncio.get_event_loop()
        _redis_coroutine = aioredis.create_redis(
            (cfg.redis_url, 6379), loop=_loop)
        self.redis = _loop.run_until_complete(_redis_coroutine)
        self.sentry = raven.Client(cfg.raven_client_url)

    async def command_is_disabled(self, guild, command_name):
        return await self.redis.exists(f'disabled:{guild.id}:{command_name}')

    async def disable_command(self, guild, command_name):
        logger.info('disabling %s in %d', command_name, guild.id)
        await self.redis.set(f'disabled:{guild.id}:{command_name}', 'on')

    async def enable_command(self, guild, command_name):
        logger.info('enabling %s in %d', command_name, guild.id)
        await self.redis.delete(f'disabled:{guild.id}:{command_name}')

    async def wait_for_response(self, ctx):
        def check(m):
            return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
        return await self.wait_for('message', check=check)

    def has_prefix(self, haystack):
        for prefix in self.command_prefix:
            if haystack.startswith(prefix):
                return True
        return False

    async def send_modlog(self, guild, *args, **kwargs):
        mod_log = discord.utils.get(guild.channels, name='mod-log')

        # don't post to mod-log, couldn't find the channel
        if mod_log is None:
            return

        await mod_log.send(*args, **kwargs)

    async def ok(self, ctx, emoji='\N{OK HAND SIGN}'):
        try:
            await ctx.message.add_reaction(emoji)
        except discord.Forbidden:
            await ctx.send(emoji)

    async def on_ready(self):
        logger.info('BOT IS READY')
        logger.info('owner id: %s', cfg.owner_id)
        logger.info('logged in')
        logger.info(f' name: {self.user.name}#{self.user.discriminator}')
        logger.info(f' id:   {self.user.id}')

        # helpful game
        short_prefix = min(self.command_prefix, key=len)
        help_game = discord.Game(name=f'{short_prefix}help')
        await self.change_presence(game=help_game)

    async def monitor_send(self, *args, **kwargs):
        monitor_channels = getattr(cfg, 'owner_monitor_channels', [])
        channels = [self.get_channel(c) for c in monitor_channels]

        # no monitor channels
        if not channels:
            return

        for channel in channels:
            await channel.send(*args, **kwargs)

    async def on_guild_join(self, g):
        diff = pretty_timedelta(datetime.datetime.utcnow() - g.created_at)
        fmt = (f'\N{SMIRKING FACE} Added to new guild "{g.name}" (`{g.id}`)'
               f', {len(g.members)} members, owned by {g.owner.mention}'
               f' (`{g.owner.id}`). This guild was created {diff} ago.')
        await self.monitor_send(fmt)

    async def on_guild_remove(self, g):
        fmt = (f'\N{LOUDLY CRYING FACE} Removed from guild "{g.name}"'
               f' (`{g.id}`)!')
        await self.monitor_send(fmt)

    async def config_is_set(self, guild, name):
        return await self.redis.exists(f'{guild.id}:{name}')

    async def on_command_error(self, ex, ctx):
        if ctx.command:
            see_help = f'Run `d?help {ctx.command.name}` for more information.'

        if isinstance(ex, commands.errors.BadArgument):
            message = str(ex)
            if not message.endswith('.'):
                message = message + '.'
            await ctx.send(f'Bad argument! {message} {see_help}')
        elif isinstance(ex, commands.errors.MissingRequiredArgument):
            await ctx.send(f'Uh oh! {ex} {see_help}')
        elif isinstance(ex, commands.NoPrivateMessage):
            await ctx.send('You can\'t do that in a private message.')
        elif isinstance(ex, errors.InsufficientPermissions):
            await ctx.send(ex)
        elif isinstance(ex, commands.errors.CommandInvokeError):
            tb = ''.join(traceback.format_exception(
                type(ex.original), ex.original,
                ex.original.__traceback__
            ))

            header = f'Command error: {type(ex.original).__name__}: {ex.original}'
            message = header + '\n' + str(tb)

            # dispatch the message
            self.sentry.captureMessage(message)
            logger.error(message)
