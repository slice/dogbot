""" This is a script that deploys Dogbot. """

import os
from pathlib import Path

from ruamel.yaml import YAML
import requests

# load the webhook url from the configuration
with open('config.yml') as f:
    webhook_url = YAML(typ='safe').load(f)['monitoring']['health_webhook']


def info(text):
    print('\033[32m[info]\033[0m', text)


def post(content=None, *, embed=None, wait_for_server=True):
    info('POSTing to {}: {}'.format(webhook_url, content or embed))
    payload = {'content': content, 'embeds': [embed]}
    requests.post(webhook_url + ('?wait=true' if wait_for_server else ''), json=payload)


def deploy():
    """ Deploys Dogbot. """

    # resolve path to playbook
    playbook = (Path.cwd() / 'deployment' / 'playbook.yml').resolve()
    info('Path to Ansible playbook: {}'.format(playbook))

    # post!
    post(embed={'title': 'Deployment starting.', 'description': 'This shouldn\'t take too long.', 'color': 0xe67e22})

    # run the playbook
    info('Running Ansible playbook.')
    exit_code = os.system('ansible-playbook {}'.format(playbook))
    if exit_code != 0:
        info('Deployment failed.')
        return
    info('Finished running playbook.')

    # post!
    post(embed={'title': 'Deployment finished.', 'description': 'The bot is restarting. This can take a bit.',
                'color': 0x2ecc71})

if __name__ == '__main__':
    deploy()
