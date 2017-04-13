from discord.ext import commands

mod_names = [
    'Moderator', 'Mod',  # classic mod role names
    'moderator', 'mod',  # lowercase mod role names
    # dog specific
    'Dog Moderator', 'Woofer', 'woofer', 'dog moderator',
    'dog mod',
]

def config_is_set(name):
    async def _predicate(ctx):
        return await ctx.bot.config_is_set(ctx.guild, name)

    return commands.check(_predicate)


def is_moderator():
    async def _predicate(ctx):
        names = [r.name for r in ctx.author.roles]
        has_moderator_role = any([1 for name in names if name in mod_names])
        return has_moderator_role
    return commands.check(_predicate)
