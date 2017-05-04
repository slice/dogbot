"""
Errors raised by Dogbot.
"""

from discord.ext import commands


class InsufficientPermissions(commands.CommandError):
    """
    A subclass of :class:`commands.CommandError` that is raised when the bot
    does not sufficient permissions to carry out a task. This is only raised
    by `dog.core.checks.bot_perms`.

    This error is specialized so that `on_command_error` can distinguish it and
    provide a human-friendly error message, so administrators/moderators can
    idenitify which permissions they need to grant the bot
    """
    pass
