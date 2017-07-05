import asyncio
import logging
import os
import sys

from discord.ext import commands

from dog import DogBot
from dog.core.bot import DogSelfbot

try:
    import dog_config as cfg
except ModuleNotFoundError:
    print('err: dog_config.py not found', file=sys.stderr)
    print('err: please read the README.md file.', file=sys.stderr)
    sys.exit(-1)

# configure logging
# set the root logger's info to INFO
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# formatters
console_fmt = logging.Formatter('[{asctime}] [{levelname: <7}] {name}: {message}', '%I:%M:%S %p', style='{')
nice_fmt = logging.Formatter('%(asctime)s [%(name)s %(levelname)s] %(message)s', '%m/%d/%Y %I:%M:%S %p')

logging.getLogger('discord').setLevel(logging.INFO)
logging.getLogger('dog').setLevel(logging.DEBUG)

# main file handler, only info
file_handler = logging.FileHandler(filename='dog.log', encoding='utf-8')
file_handler.setFormatter(nice_fmt)

# stream handler (stdout)
stream = logging.StreamHandler()
stream.setFormatter(console_fmt)

# handle from all logs
root_logger.addHandler(stream)
root_logger.addHandler(file_handler)

logger = logging.getLogger('dog')

logger.info('Bot is starting...')

try:
    import uvloop

    # uvloop for speedups
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.info('Using uvloop\'s event loop policy.')
except ModuleNotFoundError:
    pass


# gather additional options from the configuration file
additional_options = getattr(cfg, 'options', {})
additional_options.update({
    'owner_id': getattr(cfg, 'owner_id', None),
    'postgresql_auth': getattr(cfg, 'postgresql_auth', None),
    'redis_url': getattr(cfg, 'redis_url', None)
})

logger.info('Bot options: %s', additional_options)

# create dogbot instance
selfbot_mode = '--selfbot' in ' '.join(sys.argv)
if selfbot_mode:
    logger.warning('Running in selfbot mode!')
    additional_options['postgresql_auth']['database'] = 'dog_selfbot'
    d = DogSelfbot(**additional_options)
    d.load_exts_recursively('dog/selfext', 'Initial selfbot recursive load')
else:
    d = DogBot(**additional_options)
    d.load_exts_recursively('dog/ext', 'Initial recursive load')
d.run(cfg.selfbot_token if selfbot_mode else cfg.token, bot=not selfbot_mode)

# close log handlers (why)
# https://github.com/Rapptz/RoboDanny/blob/master/bot.py#L128-L132
handlers = root_logger.handlers[:]
for hndlr in handlers:
    hndlr.close()
    root_logger.removeHandler(hndlr)
