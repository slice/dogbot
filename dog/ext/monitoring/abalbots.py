"""
bots.discord.pw reporting for Dogbot.
"""
import logging

from dog import Cog

logger = logging.getLogger(__name__)


def Abalbots(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.reporting_interval = 60 * 10
        self.reporting_task = bot.loop.create_task(self.report())

    def __unload(self):
        logger.debug('Cancelling abal bot reporter task.')
        self.reporting_task.cancel()

    async def report(self):
        logger.debug('Abal bot reporter task started.')

        endpoint = f'https://bots.discord.pw/api/bots/{self.bot.user.id}/stats'
        headers = {'Authorization': self.bot.cfg['monitoring']['discordpw_token']}

        while True:
            logger.info('POSTing guild count to abal\'s website...')
            guilds = len(self.bot.guilds)

            # HTTP POST to the endpoint
            async with self.bot.session.post(endpoint, json={'server_count': guilds}, headers=headers) as resp:
                if resp.status != 200:
                    # this happens a lot
                    logger.warning('Failed to post guild count, ignoring. (HTTP %d)', resp.status)
                else:
                    logger.info('Posted guild count successfully! (%d guilds)', guilds)

            await asyncio.sleep(self.reporting_interval)


def setup(bot):
    if 'discordpw_token' not in bot.cfg['monitoring']:
        logger.warning('Not going to submit guild count to Abal\'s website, not configured.')

    bot.add_cog(Abalbots(bot))
