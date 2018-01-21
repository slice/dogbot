from lifesaver.logging import setup_logging
from dog.bot import Dogbot

setup_logging()
Dogbot.with_config().run()
