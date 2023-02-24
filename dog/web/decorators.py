import functools
import logging

from quart import current_app as app
from quart import g
from quart import jsonify as json
from quart import request, session

from lifesaver.utils import Ratelimiter

log = logging.getLogger(__name__)


def ratelimit(rate, per):
    ratelimiter = Ratelimiter(rate, per)

    def wrapper(func):
        log.debug("ratelimiting %r with %d/%f", func, ratelimiter.rate, ratelimiter.per)

        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            connecting_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

            is_being_ratelimited = ratelimiter.hit(connecting_ip)
            time_remaining = ratelimiter.time_remaining(connecting_ip)

            if is_being_ratelimited:
                log.warning("%s is being ratelimited", connecting_ip)
                return (
                    json(
                        {
                            "error": True,
                            "ratelimited": True,
                            "message": "You're doing that too fast.",
                            "seconds_remaining": time_remaining,
                            "code": "RATELIMITED",
                        }
                    ),
                    429,
                )

            return await func(*args, **kwargs)

        return wrapped

    return wrapper


def guild_resolver(func):
    @functools.wraps(func)
    def wrapped(guild_id, *args, **kwargs):
        guild = g.bot.get_guild(guild_id)

        if not guild:
            return json({"error": True, "message": "Guild not found."}), 404

        return func(guild, *args, **kwargs)

    return wrapped


def require_auth(func):
    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        if "user" not in session:
            return (
                json(
                    {
                        "error": True,
                        "message": "You must be logged in to do that.",
                        "code": "NO_AUTH",
                    }
                ),
                401,
            )

        user_id = int(session["user"]["id"])
        user_object = app.bot.get_user(user_id)

        if not user_object:
            return (
                json(
                    {
                        "error": True,
                        "message": (
                            "Unknown user. I am unable to locate you on "
                            "Discord. Do you share any servers with me?"
                        ),
                        "code": "UNKNOWN_DISCORD_USER",
                    }
                ),
                401,
            )

        g.user = user_object
        return await func(*args, **kwargs)

    return wrapped
