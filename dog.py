import os
import sys

try:
    import dog_config as cfg
except ModuleNotFoundError:
    print('err: dog_config.py not found', file=sys.stderr)
    print('err: please read the README.md file.', file=sys.stderr)
    sys.exit(-1)

import logging
import asyncio
from dog import DogBot

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

# pretty formatting
console_fmt = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
nice_fmt = logging.Formatter('%(asctime)s '
                             '[%(name)s %(levelname)s] %(message)s')

# discord log should be DEBUG, but only in dog.log
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(filename='dog_debug.log', encoding='utf-8',
                                   mode='w')
file_handler.setFormatter(nice_fmt)

file_sane_handler = logging.FileHandler(filename='dog.log', encoding='utf-8',
                                        mode='w')
file_sane_handler.setFormatter(nice_fmt)
file_sane_handler.setLevel(logging.INFO)

# stream handler (stdout), only handle INFO+
stream = logging.StreamHandler()
stream.setFormatter(console_fmt)
stream.setLevel(logging.INFO)

# handle from all logs
root_logger.addHandler(stream)
root_logger.addHandler(file_handler)
root_logger.addHandler(file_sane_handler)

logger = logging.getLogger('dog')

logger.info('bot starting')

additional_options = getattr(cfg, 'options', {})
additional_options.update({
    'owner_id': getattr(cfg, 'owner_id', None)
})
logger.info('bot options: %s', additional_options)
d = DogBot(command_prefix=cfg.prefix, **additional_options)

exts = 'dog/ext'
d_exts = [p.replace('.py', '') for p in os.listdir(exts) if p != '__pycache__']

for ext in d_exts:
    logger.info('loading extension dog.ext.%s', ext)
    d.load_extension(f'dog.ext.{ext}')

d.run(cfg.token)
