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
                             '[%(name)s %(levelname)s] %(message)s')

# discord log should be DEBUG, but only in dog.log
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.DEBUG)

# debug file handler, includes debug
file_handler = logging.FileHandler(filename='dog_debug.log', encoding='utf-8',
                                   mode='w')
file_handler.setFormatter(nice_fmt)

# main file handler, only info
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

# gather additional options from the configuration file
additional_options = getattr(cfg, 'options', {})
additional_options.update({
    'owner_id': getattr(cfg, 'owner_id', None)
})

logger.info('bot options: %s', additional_options)

# create dogbot instance
d = DogBot(command_prefix=commands.when_mentioned_or(*cfg.prefixes),
           **additional_options)

def ext_filter(f):
    return f not in ('__init__.py', '__pycache__') and not f.endswith('.pyc')

exts = []

# walk the ext directory to find extensions
for path, dirs, files in os.walk('dog/ext'):
    exts += [path.replace('/', '.') + '.' + file.replace('.py', '')
             for file in filter(ext_filter, files)]

for ext in exts:
    logger.info('Initial extension load: %s', ext)
    d.load_extension(ext)

d.run(cfg.token)
