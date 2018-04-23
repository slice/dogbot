from quart import Blueprint, jsonify as json, g
from .decorators import require_auth

api = Blueprint('api', __name__)


def inflate_guild(g):
    return {
        "id": str(g.id), "name": g.name, "members": g.member_count,
        "owner": {"id": g.owner.id, "tag": str(g.owner)},
        "icon_url": g.icon_url
    }


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
        inflate_guild(guild) for guild in g.bot.guilds
        if g.bot.guild_configs.can_edit(g.user, guild)
    ]
    return json(guilds)
