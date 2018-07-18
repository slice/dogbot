import functools

from quart import current_app as app, g, session, jsonify


def guild_resolver(func):
    @functools.wraps(func)
    def wrapped(guild_id, *args, **kwargs):
        guild = g.bot.get_guild(guild_id)

        if not guild:
            return jsonify({
                'error': True,
                'message': 'Guild not found.'
            }), 404

        return func(guild, *args, **kwargs)

    return wrapped


def require_auth(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if 'user' not in session:
            return jsonify({
                'error': True,
                'message': 'You must be logged in to do that.',
                'code': 'NO_AUTH',
            }), 401

        user_id = int(session['user']['id'])
        user_object = app.bot.get_user(user_id)

        if not user_object:
            return jsonify({
                'error': True,
                'message': ('Unknown user. I am unable to locate you on '
                            'Discord. Do you share any servers with me?'),
                'code': 'UNKNOWN_DISCORD_USER',
            }), 401

        g.user = user_object
        return func(*args, **kwargs)

    return wrapped
