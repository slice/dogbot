import aioredis
import datetime
import logging
import discord
import traceback
from discord.ext import commands
from dog.util import pretty_timedelta
import dog_config as cfg

logger = logging.getLogger(__name__)


class DogBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.boot_time = datetime.datetime.utcnow()

    async def on_ready(self):
        logger.info('BOT IS READY')
        logger.info('owner id: %s', cfg.owner_id)
        logger.info('logged in')
        logger.info(f' name: {self.user.name}#{self.user.discriminator}')
        logger.info(f' id:   {self.user.id}')

        # redis
        self.redis = await aioredis.create_redis(
            (cfg.redis_url, 6379), loop=self.loop)

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
        tb = traceback.format_exception(None, ex, ex.__traceback__)
        logger.error('command error: %s', ''.join(tb))

        if isinstance(ex, commands.errors.BadArgument):
            message = str(ex)
            if not message.endswith('.'):
                message = message + '.'
            await ctx.send(f'Bad argument. {message}')
