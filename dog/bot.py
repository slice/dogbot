import aioredis
import datetime
import logging
import discord
import traceback
from discord.ext import commands
import dog_config as cfg

logger = logging.getLogger(__name__)


class DogBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.boot_time = datetime.datetime.utcnow()

    async def on_ready(self):
        logger.info('owner id: %s', cfg.owner_id)
        logger.info('logged in as %s', self.user.id)
        print('logged in')
        print(f' name: {self.user.name}#{self.user.discriminator}')
        print(f' id:   {self.user.id}')

        # redis
        self.redis = await aioredis.create_redis(
            (cfg.redis_url, 6379), loop=self.loop)

        # helpful game
        short_prefix = min(self.command_prefix, key=len)
        help_game = discord.Game(name=f'{short_prefix}help')
        await self.change_presence(game=help_game)

    async def config_is_set(self, guild, name):
        logger.info('checking config: %d:%s', guild.id, name)
        return await self.redis.exists(f'{guild.id}:{name}')

    async def on_command_error(self, ex, ctx):
        tb = traceback.format_exception(None, ex, ex.__traceback__)
        logger.error('command error: %s', ''.join(tb))

        if isinstance(ex, commands.errors.BadArgument):
            message = str(ex)
            if not message.endswith('.'):
                message = message + '.'
            await ctx.send(f'Bad argument. {message}')
