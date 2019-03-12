import secrets
from urllib.parse import quote_plus
from typing import Tuple

import aiohttp
from quart import Blueprint, g, jsonify as json, redirect, request, session

auth = Blueprint('auth', __name__)
API_BASE = 'https://discordapp.com/api/v6'


def redirect_url() -> Tuple[str, str]:
    """Generate a redirect URL, returning the state and URL."""
    state = secrets.token_hex(64)

    client_id = g.bot.config.oauth['client_id']
    redirect_uri = g.bot.config.oauth['redirect_uri']

    url = (
        f'https://discordapp.com/oauth2/authorize'
        f'?client_id={client_id}'
        f'&redirect_uri={quote_plus(redirect_uri)}'
        '&response_type=code'
        '&scope=identify'
        f'&state={state}'
    )

    return state, url


async def fetch_user(bearer: str) -> dict:
    """Fetch information about a user from their bearer token."""
    headers = {'Authorization': f'Bearer {bearer}'}
    async with aiohttp.ClientSession(headers=headers, raise_for_status=True) as sess:
        resp = await sess.get(f'{API_BASE}/users/@me')
        return await resp.json()


async def fetch_access_token(code: str, *, refresh: bool = False) -> str:
    ENDPOINT = f'{API_BASE}/oauth2/token'

    data = {
        'client_id': str(g.bot.config.oauth['client_id']),
        'client_secret': g.bot.config.oauth['client_secret'],
        'grant_type': 'authorization_code',
        'redirect_uri': g.bot.config.oauth['redirect_uri'],
    }

    if refresh:
        data['refresh_token'] = code
    else:
        data['code'] = code

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    async with aiohttp.ClientSession(raise_for_status=True) as sess:
        resp = await sess.post(ENDPOINT, data=data, headers=headers)
        data = await resp.json()
        return data['access_token']


@auth.route('/redirect')
async def auth_redirect():
    if session.get('oauth_state') != request.args.get('state'):
        return 'invalid state', 401

    if 'code' not in request.args:
        return 'no code', 400

    access_token = await fetch_access_token(request.args['code'])
    session['token'] = access_token

    user = await fetch_user(access_token)
    session['user'] = user

    return redirect('/guilds')


@auth.route('/logout')
def auth_logout():
    if 'token' in session:
        del session['token']
        del session['user']
    return redirect('/')


@auth.route('/login')
def auth_login():
    state, url = redirect_url()
    session['oauth_state'] = state
    return redirect(url)


@auth.route('/profile')
async def auth_profile():
    active = 'token' in session

    if not active:
        return json(None)

    return json(session['user'])
