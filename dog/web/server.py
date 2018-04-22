import random
from urllib.parse import quote_plus

import aiohttp
from sanic import Sanic, response
from sanic_session import InMemorySessionInterface

app = Sanic(__name__)
session_interface = InMemorySessionInterface()
app.bot = None

REDIRECT_URI = 'http://0.0.0.0:8080'
API_BASE = 'https://discordapp.com/api/v6'


def redirect_url():
    state = hex(random.getrandbits(256))[2:]
    url = API_BASE + '/oauth2/authorize?client_id='
    url += str(app.bot.cfg.oauth['client_id'])
    url += f'&redirect_uri={quote_plus(REDIRECT_URI)}%2Fauth%2Fredirect'
    url += f'&response_type=code&scope=identify&state={state}'
    return state, url


async def get_user(bearer):
    headers = {'Authorization': 'Bearer ' + bearer}
    async with aiohttp.ClientSession(headers=headers) as session:
        return await (await session.get(API_BASE + '/users/@me')).json()


async def get_access_token(code):
    ENDPOINT = API_BASE + '/oauth2/token'
    data = {
        'client_id': str(app.bot.cfg.oauth['client_id']),
        'client_secret': app.bot.cfg.oauth['client_secret'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI + '/auth/redirect'
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        response = await session.post(ENDPOINT, data=data, headers=headers)
        return (await response.json())['access_token']


@app.middleware('request')
async def before_add(request):
    await session_interface.open(request)


@app.middleware('response')
async def after_add(request, response):
    await session_interface.save(request, response)


@app.route('/api/status')
async def api_ping(_request):
    return response.json({
        'ready': app.bot.is_ready(),
        'ping': app.bot.latency,
        'guilds': len(app.bot.guilds),
    })


@app.route('/dashboard')
async def dashboard(req):
    if 'token' not in req['session']:
        return response.redirect('/auth/login')
    return response.text('this should be the dashboard.')


@app.route('/auth/redirect')
async def auth_redirect(req):
    if req['session'].get('oauth_state') != req.args['state'][0]:
        return response.text('invalid state', status=401)
    if 'code' not in req.args:
        return response.text('no code', status=400)
    access_token = await get_access_token(req.args['code'][0])
    req['session']['token'] = access_token
    user = await get_user(access_token)
    req['session']['user'] = user
    return response.redirect('/dashboard')


@app.route('/auth/login')
async def auth_login(req):
    state, url = redirect_url()
    req['session']['oauth_state'] = state
    return response.redirect(url)
