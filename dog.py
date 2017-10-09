print('[dog] early startup')

import argparse
import asyncio
import logging

from ruamel.yaml import YAML

from dog import Dogbot
from dog.core.utils import setup_logging

parser = argparse.ArgumentParser(description='Dogbot.')
parser.add_argument('--docker', action='store_true', help='Enables Docker mode.', default=False)
args = parser.parse_args()

# load yaml configuration
print('[dog] reading configuration')
with open('config.yml', 'r') as config_file:
    cfg = YAML(typ='safe').load(config_file)

print('[dog] setting up logging')
setup_logging()

logger = logging.getLogger('dog')
logger.info('Bot is starting...')

try:
    print('[dog] importing uvloop')
    import uvloop

    # uvloop for speedups
    print('[dog] setting policy')
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.info('Using uvloop\'s event loop policy.')
except ModuleNotFoundError:
    print('[dog] uvloop not found')
    pass

if args.docker:
    logger.info('Running in Docker mode.')

    # manually patch config to work with docker-compose
    cfg['docker'] = True
    cfg['db']['redis'] = 'redis'
    cfg['db']['postgres'] = {
        'user': 'dogbot',
        'database': 'dogbot',
        'password': 'dogbot',
        'host': 'postgres'
    }
    logger.debug('Finished patching database configuration: %s', cfg['db'])

# additional options are passed directly to the bot as kwargs
additional_options = cfg['bot'].get('options', {})
additional_options.update({
    'owner_id': getattr(cfg, 'owner_id', None)
})

logger.info('Bot options: %s', additional_options)

# create and run the bot
print('[dog] creating instance')
d = Dogbot(cfg=cfg, **additional_options)

print('[dog] loading extensions')
d.load_extensions('dog/ext', 'Initial recursive load')

print('[dog] running')
d.run(cfg['tokens']['bot'])
print('[dog] run() exit')

print('[dog] exit')
