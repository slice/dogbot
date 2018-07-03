import datetime
import re

import discord

from dog.ext.gatekeeper.core import Block, Check, Report


class BlockDefaultAvatarCheck(Check):
    """A gatekeeper check that bounces users with a default avatar."""
    key = 'block_default_avatar'
    description = 'Blocks all users with a default avatar.'

    async def check(self, _, member: discord.Member):
        if member.default_avatar_url == member.avatar_url:
            raise Block('Has default avatar')


class BlockBotsCheck(Check):
    """A gatekeeper check that bounces all bots."""
    key = 'block_bots'
    description = "Blocks all bots from joining."

    async def check(self, _, member: discord.Member):
        if member.bot:
            raise Block('Blocking all bots')


class MinimumCreationTimeCheck(Check):
    """A gatekeeper check that checks the minimum creation time of a user."""
    key = 'minimum_creation_time'
    description = (
        "Blocks users that don't meet a \"minimum creation time\" check. Specify the amount of seconds "
        "that an account has to exist for to be allowed to pass through."
    )

    async def check(self, time, member: discord.Member):
        try:
            minimum_required = int(time)
            seconds_on_discord = (datetime.datetime.utcnow() - member.created_at).total_seconds()

            if seconds_on_discord < minimum_required:
                raise Block(f'Failed minimum creation time check ({seconds_on_discord} < {minimum_required}')
        except ValueError:
            raise Report('Invalid minimum creation time, must be a valid number.')


class BlockAllCheck(Check):
    """A gatekeeper check that bounces all users that attempt to join."""
    key = 'block_all'
    description = 'Blocks all users that try to join.'

    async def check(self, _, member: discord.Member):
        raise Block('Blocking all users')


class UsernameRegexCheck(Check):
    key = 'username_regex'
    description = 'Blocks all usernames that match a regex. Specify a regex.'

    async def check(self, regex: str, member: discord.Member):
        try:
            regex = re.compile(regex)
            if regex.search(member.name):
                raise Block('Matched username regex')
        except re.error as err:
            raise Report(
                f"\N{CROSS MARK} `username_regex` was invalid: `{err}`, ignoring this check."
            )
