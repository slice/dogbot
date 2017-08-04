import functools
import sys
import logging

import bugsnag
from dog import Cog

logger = logging.getLogger(__name__)


class BugsnagReporting(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.setup_reporting()

    def setup_reporting(self):
        if 'docker' not in self.bot.cfg:
            logger.warning('Not running in Docker mode, Bugsnag project root will be inaccurate.')

        bs_cfg = self.bot.cfg['monitoring']['bugsnag']

        bugsnag.configure(api_key=bs_cfg['key'], project_root='/opt/dogbot',
                          release_stage=bs_cfg.get('stage', 'production'),
                          notify_release_stages=['production'])

        if bs_cfg.get('log_errors', False):
            logging.getLogger('dog').addHandler(bugsnag.handlers.BugsnagHandler())

    async def capture(self, ctx, ex):
        if ctx:
            user = {'id': ctx.author.id, 'name': str(ctx.author)}
            md = {
                'command_context': {
                    'invoker_id': ctx.author.id,
                    'invoker': str(ctx.author),
                    'command_content': ctx.message.content,
                    'command_clean_content': ctx.message.clean_content,
                    'place': 'dm' if not ctx.guild else 'guild',
                    'channel_id': 'n/a' if not ctx.channel else ctx.channel.id,
                    'guild_id': 'n/a' if not ctx.guild else ctx.guild.id
                }
            }
        else:
            user = None
            md = None

        # notify
        func = functools.partial(bugsnag.notify, ex, meta_data=md, user=user)
        await self.bot.loop.run_in_executor(None, func)

    async def on_error(self, event):
        type_, value, traceback = sys.exc_info()
        await self.capture(None, value)

    async def on_uncaught_command_invoke_error(self, ex, info):
        logger.info('Submitting uncaught invoke error to bugsnag.')
        await self.capture(info[2], ex)


def setup(bot):
    if 'bugsnag' not in bot.cfg['monitoring']:
        logger.warning('Not going to add bugsnag reporting, not configured!')
        return
    bot.add_cog(BugsnagReporting(bot))
