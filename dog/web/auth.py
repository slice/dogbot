import random
from urllib.parse import quote_plus

import aiohttp
from quart import Blueprint, jsonify as json, session, request, redirect, \
    url_for, g

auth = Blueprint('auth', __name__)
API_BASE = 'https://discordapp.com/api/v6'


def redirect_url():
    state = hex(random.getrandbits(256))[2:]
    url = API_BASE + '/oauth2/authorize?client_id='
    url += str(g.bot.cfg.oauth['client_id'])
    redirect_uri = g.bot.cfg.oauth['redirect_uri']
    url += f'&redirect_uri={quote_plus(redirect_uri)}'
    url += f'&response_type=code&scope=identify&state={state}'
    return state, url


async def get_user(bearer):
    headers = {'Authorization': 'Bearer ' + bearer}
    async with aiohttp.ClientSession(headers=headers) as s:
        return await (await s.get(API_BASE + '/users/@me')).json()


async def get_access_token(code):
    ENDPOINT = API_BASE + '/oauth2/token'
    data = {
        'client_id': str(g.bot.cfg.oauth['client_id']),
        'client_secret': g.bot.cfg.oauth['client_secret'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': g.bot.cfg.oauth['redirect_uri']
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    async with aiohttp.ClientSession(raise_for_status=True) as s:
        response = await s.post(ENDPOINT, data=data, headers=headers)
        return (await response.json())['access_token']


@auth.route('/redirect')
async def auth_redirect():
    if session.get('oauth_state') != request.args.get('state'):
        return 'invalid state', 401
    if 'code' not in request.args:
        return 'no code', 400
    access_token = await get_access_token(request.args['code'])
    session['token'] = access_token
    user = await get_user(access_token)
    session['user'] = user
    print(user, 'has logged in! Their session:', session)
    return redirect(url_for('dashboard'))


@auth.route('/logout')
def auth_logout():
    del session['token']
    del session['user']
    return redirect(url_for('dashboard'))


@auth.route('/login')
def auth_login():
    state, url = redirect_url()
    session['oauth_state'] = state
    return redirect(url)


@auth.route('/user')
async def auth_user():
    active = 'token' in session
    print('User request.', session)
    if not active:
        return json({'active': False})
    try:
        user = await get_user(session['token'])
        return json({'active': True, 'user': user})
    except aiohttp.ClientResponseError:
        return json({'active': False})
