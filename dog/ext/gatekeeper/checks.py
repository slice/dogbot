import datetime
import re

from dog.ext.gatekeeper.core import Block, Check, Report


class BlockDefaultAvatarCheck(Check):
    """Bounce all users with default avatars."""
    key = 'block_default_avatar'
    description = 'Blocks all users with a default avatar.'

    async def check(self, _):
        if self.member.default_avatar_url == self.member.avatar_url:
            raise Block('Has default avatar')


class BlockBotsCheck(Check):
    """Bounce all bots."""
    key = 'block_bots'
    description = "Blocks all bots from joining."

    async def check(self, _):
        if self.member.bot:
            raise Block('Blocking all bots')


class MinimumCreationTimeCheck(Check):
    """Enforce a minimum creation time."""
    key = 'minimum_creation_time'
    description = (
        "Blocks users that don't meet a \"minimum creation time\" check. Specify the amount of seconds "
        "that an account has to exist for to be allowed to pass through."
    )

    async def check(self, time):
        try:
            minimum_required = int(time)
        except ValueError:
            raise Report('Invalid minimum creation time, must be a valid number.')

        seconds_on_discord = (datetime.datetime.utcnow() - self.member.created_at).total_seconds()

        if seconds_on_discord < minimum_required:
            raise Block(f'Account too young ({seconds_on_discord} < {minimum_required}')


class BlockAllCheck(Check):
    """Bounce all users."""
    key = 'block_all'
    description = 'Blocks all users that try to join.'

    async def check(self, _):
        raise Block('Blocking all users')


class UsernameRegexCheck(Check):
    """Check usernames with regexes."""
    key = 'username_regex'
    description = 'Blocks all usernames that match a regex. Specify a regex.'

    async def check(self, pattern: str):
        try:
            if re.search(pattern, self.member.name):
                raise Block('Matched username regex')
        except re.error as err:
            raise Report(f"`username_regex` was invalid: `{err}`")
