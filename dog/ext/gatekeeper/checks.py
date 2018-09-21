__all__ = ['gatekeeper_check', 'block_default_avatars', 'block_bots',
           'minimum_creation_time', 'block_all', 'username_regex']

import datetime
import inspect
import functools
import re
import typing

import discord

from dog.ext.gatekeeper.core import Block, Report


CheckOptions = typing.Dict[str, typing.Any]


def convert_options(check, parameters, options: CheckOptions) -> typing.List[typing.Any]:
    params = []

    for name, param in parameters.items():
        # do not attempt to convert the first parameter
        if name == 'member':
            continue

        value = options.get(name)
        if value is None:
            raise Report(f'`{check.__name__}` is missing the `{name}` option.')

        annotation = param.annotation
        if annotation is inspect.Parameter.empty or isinstance(value, annotation):
            # just add the param if we don't need to convert or if the value is
            # already the desired type
            params.append(value)
        else:
            # convert the value by calling the annotation
            params.append(annotation(value))

    return params


def gatekeeper_check(func):
    """Register a function as a Gatekeeper check."""

    @functools.wraps(func)
    async def wrapped(member: discord.Member, options: CheckOptions) -> None:
        parameters = inspect.signature(func).parameters

        # only pass the options dict to the function if it accepts it
        if len(parameters) == 1:
            await discord.utils.maybe_coroutine(func, member)
        else:
            converted_options = convert_options(func, parameters, options)
            await discord.utils.maybe_coroutine(func, member, *converted_options)

    return wrapped


@gatekeeper_check
def block_default_avatars(member: discord.Member):
    if member.default_avatar_url == member.avatar_url:
        raise Block('Has no avatar')


@gatekeeper_check
def block_bots(member: discord.Member):
    if member.bot:
        raise Block('Is a bot')


@gatekeeper_check
def minimum_creation_time(member: discord.Member, minimum_age: int):
    age = (datetime.datetime.utcnow() - member.created_at).total_seconds()

    if age < minimum_age:
        raise Block(f'Account too young ({age} < {minimum_age})')


@gatekeeper_check
def block_all(_member: discord.Member):
    raise Block('Blocking all users')


@gatekeeper_check
def username_regex(member: discord.Member, regex: str):
    try:
        if re.search(regex, member.name):
            raise Block('Username matched regex')
    except re.error as err:
        raise Report(f"Invalid regex. (`{err}`)")
