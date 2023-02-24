__all__ = [
    "gatekeeper_check",
    "block_default_avatars",
    "block_bots",
    "minimum_creation_time",
    "block_all",
    "username_regex",
]

import functools
import inspect
import re
from typing import Any, Dict, List

import discord

from .core import Bounce, Report

CheckOptions = Dict[str, Any]


def convert_options(check, parameters, options: CheckOptions) -> List[Any]:
    converted = {}

    for index, (name, param) in enumerate(parameters.items()):
        # do not attempt to convert the first parameter
        if index == 0:
            continue

        try:
            value = options[name]
        except KeyError:
            if param.default is not inspect.Parameter.empty:
                # this parameter is optional, continue
                continue
            raise Report(f"`{check.__name__}` is missing the `{name}` option.")

        annotation = param.annotation
        if annotation is inspect.Parameter.empty or isinstance(value, annotation):
            # just add the param if we don't need to convert or if the value is
            # already the desired type
            converted[name] = value
        else:
            # convert the value by calling the annotation
            converted[name] = annotation(value)

    return converted


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
            await discord.utils.maybe_coroutine(func, member, **converted_options)

    return wrapped


@gatekeeper_check
def block_default_avatars(member: discord.Member):
    if member.avatar is None:
        raise Bounce("Has no avatar")


@gatekeeper_check
def block_bots(member: discord.Member):
    if member.bot:
        raise Bounce("Is a bot")


@gatekeeper_check
def minimum_creation_time(member: discord.Member, *, minimum_age: int):
    age = (discord.utils.utcnow() - member.created_at).total_seconds()

    if age < minimum_age:
        raise Bounce(f"Account too young ({age} < {minimum_age})")


@gatekeeper_check
def block_all(_member: discord.Member):
    raise Bounce("Blocking all users")


@gatekeeper_check
def username_regex(member: discord.Member, *, regex: str, case_sensitive: bool = True):
    flags = 0 if case_sensitive else re.I

    try:
        if re.search(regex, member.name, flags):
            raise Bounce("Username matched regex")
    except re.error as err:
        raise Report(f"Invalid regex. (`{err}`)")
