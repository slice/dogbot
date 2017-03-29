from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class DogBot(commands.Bot):
    async def on_ready(self):
        logger.info('logged in as %s', self.user.id)
        print('logged in')
        print(f' name: {self.user.name}#{self.user.discriminator}')
        print(f' id:   {self.user.id}')
