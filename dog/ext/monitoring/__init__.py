from .abalbots import Abalbots
from .bugsnag import BugsnagReporting
from .datadog import Datadog
from .monitorchannel import MonitorChannel
from .sentry import SentryErrorReporting


def setup(bot):
    if 'discordpw_token' in bot.cfg['monitoring']:
        bot.add_cog(Abalbots(bot))

    if 'bugsnag' in bot.cfg['monitoring']:
        bot.add_cog(BugsnagReporting(bot))

    if 'datadog' in bot.cfg['monitoring']:
        bot.add_cog(Datadog(bot))

    if 'raven_client_url' in bot.cfg['monitoring']:
        bot.add_cog(SentryErrorReporting(bot))

    bot.add_cog(MonitorChannel(bot))
