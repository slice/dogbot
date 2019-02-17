from quart import Blueprint, g, jsonify as json, request
from ruamel.yaml import YAML, YAMLError

from .decorators import require_auth

api = Blueprint('api', __name__)
yaml = YAML(typ='safe')


def inflate_guild(g):
    return {
        "id": str(g.id), "name": g.name, "members": g.member_count,
        "owner": {"id": str(g.owner.id), "tag": str(g.owner)},
        "icon_url": g.icon_url_as(format='png', size=64)
    }


@api.route('/status')
def api_ping():
    return json({
        'ready': g.bot.is_ready(),
        'ping': g.bot.latency,
        'guilds': len(g.bot.guilds)
    })


@api.route('/guild/<int:guild_id>', methods=['GET'])
@require_auth
async def api_guild(guild_id):
    guild = g.bot.get_guild(guild_id)

    if guild is None or not g.bot.guild_configs.can_edit(g.user, guild_id):
        return json({
            'error': True,
            'message': 'Unknown guild.',
            'code': 'UNKNOWN_GUILD',
        }), 404

    return json(inflate_guild(guild))


@api.route('/guild/<int:guild_id>/config', methods=['GET', 'PATCH'])
@require_auth
async def api_guild_config(guild_id):
    guild = g.bot.get_guild(guild_id)

    if guild is None or not g.bot.guild_configs.can_edit(g.user, guild_id):
        return json({
            'error': True,
            'message': 'Unknown guild.',
            'code': 'UNKNOWN_GUILD',
        }), 404

    if request.method == 'PATCH':
        text = await request.get_data(raw=False)

        try:
            yml = yaml.load(text)
        except YAMLError as err:
            return json({
                "error": True,
                "message": f"Invalid YAML ({err}).",
                "code": "INVALID_YAML"
            }), 400

        # of course, it's possible for a singular, basic scalar value to be
        # passed in
        if not isinstance(yml, dict):
            return json({
                "error": True,
                "message": "Configuration is not a dictionary (mapping).",
                "code": "INVALID_CONFIG",
            }), 400

        await g.bot.guild_configs.write(guild_id, text)
        return json({"success": True})

    config = g.bot.guild_configs.get(guild_id, yaml=True)
    return json({"guild_id": guild_id, "config": config})


@api.route('/guilds')
@require_auth
def api_guilds():
    guilds = sorted([
        inflate_guild(guild) for guild in g.bot.guilds
        if g.bot.guild_configs.can_edit(g.user, guild)
    ], key=lambda guild: guild['id'])
    return json(guilds)
