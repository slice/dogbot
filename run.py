from lifesaver.logging import setup_logging
from dog.bot import Dogbot

try:
    import uvloop
    import asyncio
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ModuleNotFoundError:
    pass

setup_logging()
Dogbot.with_config().run()
