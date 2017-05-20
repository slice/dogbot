import asyncio
import logging
import os
import sys

from discord.ext import commands

from dog import DogBot

try:
    import dog_config as cfg
except ModuleNotFoundError:
    print('err: dog_config.py not found', file=sys.stderr)
    print('err: please read the README.md file.', file=sys.stderr)
    sys.exit(-1)


try:
    import uvloop
    # uvloop for speedups
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ModuleNotFoundError:
    pass

# configure logging
# set the root logger's info to INFO
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# formatters
console_fmt = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
nice_fmt = logging.Formatter('%(asctime)s '
                             '[%(name)s %(levelname)s] %(message)s', '%m/%d/%Y %I:%M:%S %p')

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

# gather additional options from the configuration file
additional_options = getattr(cfg, 'options', {})
additional_options.update({
    'owner_id': getattr(cfg, 'owner_id', None)
})

logger.info('Bot options: %s', additional_options)

# create dogbot instance
d = DogBot(command_prefix=commands.when_mentioned_or(*cfg.prefixes),
           **additional_options)

d.load_exts_recursively('dog/ext', 'Initial recursive load')
d.run(cfg.token)

# close log handlers (why)
# https://github.com/Rapptz/RoboDanny/blob/master/bot.py#L128-L132
handlers = root_logger.handlers[:]
for hndlr in handlers:
    hndlr.close()
    root_logger.removeHandler(hndlr)
