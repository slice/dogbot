from quart import Blueprint, jsonify as json, g, request
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


@api.route('/guild/<int:guild_id>/config', methods=['GET', 'PATCH'])
@require_auth
async def api_guild_config(guild_id):
    if g.bot.get_guild(guild_id) is None:
        return 'Unknown guild', 400

    if not g.bot.guild_configs.can_edit(g.user, guild_id):
        return 'Unauthorized.', 401

    if request.method == 'PATCH':
        # TODO: handle invalid yaml etc
        await g.bot.guild_configs.write(guild_id, request.data)
        return

    config = g.bot.guild_configs.get(guild_id)
    return json({"guild_id": guild_id, "config": config})


@api.route('/guilds')
@require_auth
def api_guilds():
    guilds = [
        inflate_guild(guild) for guild in g.bot.guilds
        if g.bot.guild_configs.can_edit(g.user, guild)
    ]
    return json(guilds)
