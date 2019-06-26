import functools

from quart import Blueprint, g
from quart import jsonify as json

from .decorators import guild_resolver

quotes = Blueprint('quotes', __name__)

QUOTES_PRIVATE = {
    'error': True,
    'message': 'Guild is not configured to expose quotes.',
    'code': 'QUOTES_PRIVATE'
}


def get_quotes(guild):
    return g.bot.get_cog('Quoting').storage.get(str(guild.id), None)


def guild_exposes_quotes(guild) -> bool:
    config = g.bot.guild_configs.get(guild, {})
    return config.get('publish_quotes', False)


def quotes_resolver(func):
    @functools.wraps(func)
    def wrapper(guild, *args, **kwargs):
        if not guild_exposes_quotes(guild):
            return json(QUOTES_PRIVATE), 401
        return func(guild, *args, **kwargs)

    return wrapper


@quotes.route('/<int:guild_id>/<quote_name>', methods=['GET'])
@guild_resolver
@quotes_resolver
async def guild_quote(guild, quote_name):
    quotes = get_quotes(guild)
    quote = quotes.get(quote_name)
    if not quote:
        return json({
            'error': True,
            'message': 'Quote not found.',
            'code': 'QUOTE_NOT_FOUND',
        }), 404

    return json({'name': quote_name, **quote})


@quotes.route('/<int:guild_id>', methods=['GET'])
@guild_resolver
@quotes_resolver
async def guild_all(guild):
    quotes = get_quotes(guild)
    return json([
        {"name": name, **quote}
        for name, quote in quotes.items()
    ])
