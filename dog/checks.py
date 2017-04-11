from discord.ext import commands


def config_is_set(name):
    async def _predicate(ctx):
        return await ctx.bot.config_is_set(ctx.guild, name)

    return commands.check(_predicate)


def is_moderator():
    async def _predicate(ctx):
        looking_for = ['Moderator', 'Mod', 'moderator', 'mod', 'Dog Moderator', 'Muter']
        names = [r.name for r in ctx.author.roles]
        has_moderator_role = any([1 for name in names if name in looking_for])
        return has_moderator_role
    return commands.check(_predicate)
