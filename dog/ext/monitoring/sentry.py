"""
Sentry error reporting for Dogbot.
"""
import logging

import raven
from dog import Cog

logger = logging.getLogger(__name__)


class SentryErrorReporting(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.sentry = raven.Client(bot.cfg['monitoring']['raven_client_url'])

    async def on_uncaught_command_invoke_error(self, exception, info):
        logger.info('Capturing message for Sentry.')
        self.sentry.captureMessage(info[0])
