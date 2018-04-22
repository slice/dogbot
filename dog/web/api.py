from quart import Blueprint, jsonify as json, g
from .decorators import require_auth

api = Blueprint('api', __name__)


@api.route('/status')
def api_ping():
    return json({
        'ready': g.bot.is_ready(),
        'ping': g.bot.latency,
        'guilds': len(g.bot.guilds)
    })


@api.route('/guilds')
@require_auth
def api_guilds():
    guilds = [
        {"id": str(guild.id), "name": guild.name, "members": guild.member_count}
        for guild in g.bot.guilds if guild.owner == g.user
    ]
    return json(guilds)
