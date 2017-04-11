from discord.ext import commands


def config_is_set(name):
    async def _predicate(ctx):
        return await ctx.bot.config_is_set(ctx.guild, name)

    return commands.check(_predicate)
