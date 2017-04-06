from discord.ext import commands
from dog_config import owner_id


def is_owner():
    return commands.check(lambda ctx: ctx.message.author.id == owner_id)
