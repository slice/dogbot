from .abalbots import Abalbots
from .bugsnag import BugsnagReporting
from .datadog import Datadog
from .monitorchannel import MonitorChannel
from .sentry import SentryErrorReporting


def setup(bot):
    cogs = {
        'discordpw_token': Abalbots,
        'bugsnag': BugsnagReporting,
        'datadog': Datadog,
        'raven_client_url': SentryErrorReporting
    }

    for config_key, cog in cogs.items():
        if config_key in bot.cfg.get('monitoring', {}):
            bot.add_cog(cog(bot))

    bot.add_cog(MonitorChannel(bot))
