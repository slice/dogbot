import logging
import datetime
import urllib.parse
from html.parser import HTMLParser
from typing import Dict, Any, List, Union, Callable, Set, TypeVar, Type

import discord
import timeago
from discord import Message, Member, Embed
from discord.utils import maybe_coroutine

log = logging.getLogger(__name__)


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def user_format(format_string: str, parameters: Dict[Any, Any]) -> str:
    """Like .format, but for user input."""
    result = format_string

    for key, value in parameters.items():
        result = result.replace('{' + key + '}', str(value))

    return result


R = TypeVar('T')
ResultContainerType = Union[List, Set]

async def history_reducer(ctx, reducer: Callable[[Message], R], *,
                          ignore_duplicates=False, result_container_type: Type=list, **kwargs) -> ResultContainerType[R]:
    """
    Iterates through message history, and outputs a list of items populated by a function that receives each
    message.

    Parameters
    ----------
    ctx
        The command context.
    reducer
        The callable reducer. Results that aren't falsy are added to the result container.
    ignore_duplicates
        Specifies whether duplicates should be ignored.
    result_container_type
        Specifies the type of result container. Should be either ``list`` or ``set``.
    kwargs
        The kwargs to pass to the ``ctx.history`` class.

    Returns
    -------
        The list of items.
    """
    if 'limit' not in kwargs:
        raise TypeError('limit required')

    history: List[Message] = await ctx.history(limit=kwargs['limit']).flatten()
    results: Union[List, Set] = result_container_type()

    for message in history:
        result = await maybe_coroutine(reducer, message)

        if result:
            if ignore_duplicates and result in results:
                continue

            if isinstance(results, list):
                results.append(result)
            elif isinstance(results, set):
                results.add(results)

    return results


def format_dict(d: Dict[Any, Any], *, style='equals') -> str:
    """
    Formats a ``dict`` to appear in key-value style.

    Parameters
    ----------
    d
        The ``dict`` to format.
    style
        The style to format the dict.

    Returns
    -------
    str
        The formatted ``dict``, as a ``str``.
    """
    code_block = '```{}\n'.format('ini' if style == 'ini' else '')

    # calculate the longest key
    padding = len(max(d.keys(), key=len))

    for name, value in d.items():
        if style == 'equals':
            code_block += '{name: <{width}} = {value}\n'.format(name=name, width=padding, value=value)
        elif style == 'ini':
            code_block += '{name: <{width}} {value}\n'.format(name=f'[{name}]', width=padding + 2, value=value)

    return code_block + '```'


def prevent_codeblock_breakout(text: str) -> str:
    """
    Formats text to prevent "breaking out" of a codeblock.

    Parameters
    ----------
    text
        The text to format.

    Returns
    -------
    str
        The formatted text.
    """
    return text.replace('`', '\u200b`\u200b')


def make_profile_embed(member: Member) -> Embed:
    """
    Creates an embed with the author containing the :class:`discord.Member`'s username and discriminator, along
    with their icon.

    Parameters
    ----------
    member
        The member to use in the :class:`discord.Embed`

    Returns
    -------
    :class:`discord.Embed`
        The resulting embed.
    """
    return Embed().set_author(name=str(member), icon_url=member.avatar_url)


def codeblock(text: str, *, lang: str='') -> str:
    """
    Formats a codeblock.

    Parameters
    ----------
    text
        The text to be inside of the codeblock.
    lang
        The language to use.

    Returns
    -------
    str
        The formatted message.
    """
    return f'```{lang}\n{text}\n```'


def strip_tags(text: str) -> str:
    """
    Strips HTML tags from text.

    Parameters
    ----------
    text
        The text to strip.

    Returns
    -------
    str
        The stripped text.
    """
    s = MLStripper()
    s.feed(text)
    return s.get_data()


def urlescape(text: str) -> str:
    """
    Quotes text using urllib to be included in URIs.

    Parameters
    ----------
    text
        The text to quote.

    Returns
    -------
    str
        The quoted text.
    """
    return urllib.parse.quote_plus(text)


def standard_datetime(dt: datetime.datetime):
    """
    Returns a string representing a :class:`datetime.datetime` formatted a nice way: ::

        YEAR-MONTH-DAY HOUR:MINUTE:SECOND

    Parameters
    ----------
    dt
        The :class:`datetime.datetime` to format.
    """
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def format_list(lst: List[Any]) -> str:
    """
    Returns a string representing a list as an ordered list. List numerals are padded to ensure that there are at
    least 3 digits.

    Parameters
    ----------
    lst
        The list to format.

    Returns
    -------
    str
        The formatted string.
    """
    return '\n'.join('`{:03d}`: {}'.format(index + 1, value) for index, value in enumerate(lst))


def now() -> str:
    """
    Returns a string representing the current time, formatted with :func:`standard_datetime`.
    """
    """ Returns an Semistandard-formatted datetime with a "UTC" suffix. """
    return standard_datetime(datetime.datetime.utcnow()) + ' UTC'


def ago(dt: datetime.datetime) -> str:
    """
    Returns a string representing the amount of time since a datetime.

    Parameters
    ----------
    dt
        The datetime to process.
    """
    return timeago.format(dt, datetime.datetime.utcnow())


def truncate(text: str, desired_length: int):
    """
    Truncates text to a desired length.

    If the text is truncated, the last three characters are overwritten with ``...``

    Parameters
    ----------
    text
        The text to truncate.
    desired_length
        The desired length.

    Returns
    -------
    str
        The truncated string.
    """
    if len(text) > desired_length:
        return text[:desired_length - 3] + '...'
    return text


def commas(number: Union[int, float]) -> str:
    """
    Adds American-style commas to an number, then returns it as a str.
    """
    return '{:,d}'.format(number)


def filesize(byte_size: int) -> str:
    """
    Converts an byte size to a human-readable filesize.

    At this time, it only supports MB and KB.

    Parameters
    ----------
    byte_size
        The amount of bytes.

    Returns
    -------
    str
        The human-readable filesize.
    """
    if bytes > 10 ** 5 * 5:  # 0.5 MB
        return f'{round(byte_size / 10 ** 6, 2)} MB'
    else:
        return f'{round(byte_size / 1000, 2)} KB'


def describe(thing: Any, *, mention=False, before='', created=False, joined=False, quote=False):
    """
    Returns a string representing an project. Usually consists of the object in string form,
    then the object's ID in parentheses after.

    Parameters
    ----------
    thing
        The thing to describe. Usually a superclass of :class:`discord.Object`.
    mention
        Specifies whether to mention the thing instead of using its string representation.
    before
        Specifies text to insert after name and ID.
    created
        Specifies whether to append the ``created_at`` attribute, post-processed with :func:`ago`.
    joined
        Specifies whether to append the ``joined_at`` attribute, post-processed with :func:`ago`.
    quote
        Specifies whether to quote the name of the thing.
    """

    # get name, might be mention
    name = str(thing) if not mention else thing.mention

    # handle emoji specially
    if isinstance(thing, discord.Emoji):
        name = f'`{":" + thing.name + ":" if thing.require_colons else thing.name}`'

    if quote:
        name = '"' + name + '"'

    # name + id
    message = f'{name} (`{thing.id}`)'

    # objects have id only
    if isinstance(thing, discord.Object):
        message = f'`{thing.id}`'

    if before:
        message += ' ' + before
    if created:
        message += f', created {ago(thing.created_at)}'
    if joined and isinstance(thing, discord.Member):
        message += f', joined {ago(thing.joined_at)}'
    return message
