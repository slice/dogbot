import datetime
import logging
import discord
import traceback
from discord.ext import commands
import dog_config as cfg

logger = logging.getLogger(__name__)


class DogBot(commands.Bot):
    async def on_ready(self):
        self.boot_time = datetime.datetime.utcnow()

        logger.info('owner id: %s', cfg.owner_id)
        logger.info('logged in as %s', self.user.id)
        print('logged in')
        print(f' name: {self.user.name}#{self.user.discriminator}')
        print(f' id:   {self.user.id}')

        # helpful game
        short_prefix = min(self.command_prefix, key=len)
        help_game = discord.Game(name=f'{short_prefix}help')
        await self.change_presence(game=help_game)

    async def on_command_error(self, ex, ctx):
        tb = traceback.format_exception(None, ex, ex.__traceback__)
        logger.error('command error: %s', ''.join(tb))
