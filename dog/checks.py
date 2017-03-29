from discord.ext import commands

owner_id = '97104885337575424'

def is_owner():
    return commands.check(lambda ctx: ctx.message.author.id == owner_id)
