import functools

from quart import session, current_app as app, g


def require_auth(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if 'user' not in session:
            return 'Unauthorized.', 401
        user_id = int(session['user']['id'])
        user_object = app.bot.get_user(user_id)
        if not user_object:
            return 'Who are you? Unknown user.', 401
        g.user = user_object
        return func(*args, **kwargs)
    return wrapped
