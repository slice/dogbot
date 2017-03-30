try:
    import dog_config as cfg
except ModuleNotFoundError:
    print('err: dog_config.py not found')

import logging
import asyncio
import uvloop
from os import listdir
from dog import DogBot

# uvloop for speedups
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# configure logging
# set the root logger's info to INFO
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# pretty formatting
nice_fmt = logging.Formatter('%(asctime)s [%(name)s %(levelname)s] %(message)s')

# discord log should be DEBUG, but only in dog.log
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(filename='dog.log', encoding='utf-8',
                                   mode='w')
file_handler.setFormatter(nice_fmt)

# stream handler (stdout), only handle INFO+
stream = logging.StreamHandler()
stream.setFormatter(nice_fmt)
stream.setLevel(logging.INFO)

# handle from all logs
root_logger.addHandler(stream)
root_logger.addHandler(file_handler)

logger = logging.getLogger('dog')

logger.info('bot starting')

d = DogBot(command_prefix=cfg.prefix)

d_exts = [p.replace('.py', '') for p in listdir('dog/ext') if p != '__pycache__']

for ext in d_exts:
    logger.info('loading extension dog.ext.%s', ext)
    d.load_extension(f'dog.ext.{ext}')

d.run(cfg.token)
