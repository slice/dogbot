from typing import cast, Any

import discord
from quart import Blueprint, g
from quart import jsonify as json
from quart import request
from ruamel.yaml import YAML, YAMLError

from dog.bot import TYPE_CHECKING

from .decorators import require_auth

if TYPE_CHECKING:
    from dog.bot import Dogbot

api = Blueprint("api", __name__)
yaml = YAML(typ="safe")


def global_bot() -> "Dogbot":
    return cast("Dogbot", g.bot)


def inflate_guild(guild: discord.Guild) -> dict[str, Any]:
    icon = guild.icon
    if icon is not None:
        icon = icon.replace(size=64, format="png")
    assert guild.owner is not None  # when can this be None, though?

    return {
        "id": str(guild.id),
        "name": guild.name,
        "members": guild.member_count,
        "owner": {"id": str(guild.owner.id), "tag": str(guild.owner)},
        "icon_url": str(icon),
    }


@api.route("/status")
async def api_ping():
    bot = global_bot()

    return json(
        {"ready": bot.is_ready(), "ping": bot.latency, "guilds": len(bot.guilds)}
    )


@api.route("/guild/<int:guild_id>", methods=["GET"])
@require_auth
async def api_guild(guild_id):
    bot = global_bot()
    guild = bot.get_guild(guild_id)

    if guild is None or not bot.guild_configs.can_edit(g.user, guild_id):
        return (
            json(
                {
                    "error": True,
                    "message": "Unknown guild.",
                    "code": "UNKNOWN_GUILD",
                }
            ),
            404,
        )

    return json(inflate_guild(guild))


@api.route("/guild/<int:guild_id>/config", methods=["GET", "PATCH"])
@require_auth
async def api_guild_config(guild_id):
    guild = global_bot().get_guild(guild_id)

    if guild is None or not g.bot.guild_configs.can_edit(g.user, guild_id):
        return (
            json(
                {
                    "error": True,
                    "message": "Unknown guild.",
                    "code": "UNKNOWN_GUILD",
                }
            ),
            404,
        )

    if request.method == "PATCH":
        text = await request.get_data(as_text=True)

        try:
            yml = yaml.load(text)
        except YAMLError as err:
            return (
                json(
                    {
                        "error": True,
                        "message": f"Invalid YAML ({err}).",
                        "code": "INVALID_YAML",
                    }
                ),
                400,
            )

        if not g.bot.guild_configs.can_edit(g.user, guild_id, with_config=yml):
            return (
                json(
                    {
                        "error": True,
                        "message": "This configuration will lock you out. Make sure to add yourself as an editor.",
                        "code": "SELF_LOCKOUT",
                    }
                ),
                403,
            )

        # of course, it's possible for a singular, basic scalar value to be
        # passed in
        if yml is not None and not isinstance(yml, dict):
            return (
                json(
                    {
                        "error": True,
                        "message": "This configuration isn't a mapping.",
                        "code": "INVALID_CONFIG",
                    }
                ),
                400,
            )

        await g.bot.guild_configs.write(guild_id, text)
        return json({"success": True})

    config = g.bot.guild_configs.get(guild_id, yaml=True)
    return json({"guild_id": guild_id, "config": config})


@api.route("/guilds")
@require_auth
async def api_guilds():
    guilds = sorted(
        [
            inflate_guild(guild)
            for guild in g.bot.guilds
            if g.bot.guild_configs.can_edit(g.user, guild)
        ],
        key=lambda guild: guild["id"],
    )
    return json(guilds)
