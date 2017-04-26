from discord.ext import commands


class InsufficientPermissions(commands.CommandError):
    """
    A subclass of :class:`commands.CommandError` that is raised when the bot
    does not sufficient permissions to carry out a task. This is only raised
    by :class:`core.checks.bot_perms`.
    """
    pass
