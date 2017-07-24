import asyncio
import logging
import sys

from ruamel.yaml import YAML

from dog import DogBot

# load yaml configuration
with open('config.yml', 'r') as config_file:
    cfg = YAML(typ='safe').load(config_file)

# configure logging, and set the root logger's info to INFO
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# formatters
console_fmt = logging.Formatter('[{asctime}] [{levelname: <7}] {name}: {message}', '%I:%M:%S %p', style='{')
nice_fmt = logging.Formatter('%(asctime)s [%(name)s %(levelname)s] %(message)s', '%m/%d/%Y %I:%M:%S %p')

# enable debug logging for us, but not for discord
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

is_docker = '--docker' in ' '.join(sys.argv)
if is_docker:
    logger.info('Running in Docker mode.')
    cfg['db']['redis'] = 'redis'
    cfg['db']['postgres'] = {
        'user': 'dogbot',
        'database': 'dogbot',
        'password': 'dogbot',
        'host': 'postgres'
    }
    logger.debug('Finished database configuration: %s', cfg['db'])

# additional options are passed directly to the bot as kwargs
additional_options = cfg['bot'].get('options', {})
additional_options.update({
    'owner_id': getattr(cfg, 'owner_id', None)
})

logger.info('Bot options: %s', additional_options)

# create and run the bot
d = DogBot(cfg=cfg, **additional_options)
d.load_exts_recursively('dog/ext', 'Initial recursive load')
d.run(cfg['tokens']['bot'])

# close log handlers (why)
# https://github.com/Rapptz/RoboDanny/blob/master/bot.py#L128-L132
handlers = root_logger.handlers[:]
for hndlr in handlers:
    hndlr.close()
    root_logger.removeHandler(hndlr)
