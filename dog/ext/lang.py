import os

import discord
from discord.ext import commands
from dog import Cog


class LangConverter(commands.Converter):
    async def convert(self, ctx, arg):
        if arg == 'default':
            return ''
        if len(arg) != 5:
            raise commands.BadArgument('Languages are 5 letters long, like so: `en-US`')
        if not os.path.isfile(f'./resources/lang/{arg}.yml'):
            raise commands.BadArgument('That language isn\'t supported.')
        return arg


class Lang(Cog):
    @commands.command(aliases=['sml'])
    async def set_my_lang(self, ctx, lang: LangConverter):
        """ Sets your preferred language. """
        await ctx.bot.redis.set(f'i18n:user:{ctx.author.id}:lang', lang)
        await ctx.ok()

    @commands.command(aliases=['sgl', 'ssl'])
    @commands.has_permissions(manage_guild=True)
    async def set_server_lang(self, ctx, lang: LangConverter):
        """ Sets the preferred language for this guild. """
        await ctx.bot.redis.set(f'i18n:guild:{ctx.guild.id}:lang', lang)
        await ctx.ok()


def setup(bot):
    bot.add_cog(Lang(bot))
