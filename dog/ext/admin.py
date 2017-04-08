import os
import sys
import inspect
import logging
import re
import discord
from time import monotonic
from discord.ext import commands
from dog import Cog
from dog.haste import haste

logger = logging.getLogger(__name__)


class Admin(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eval_last_result = None

    @commands.command()
    async def ping(self, ctx):
        """ You know what this does. """
        begin = monotonic()
        msg = await ctx.send('Pong!')
        end = monotonic()
        difference_ms = round((end - begin) * 1000, 2)
        await msg.edit(content=f'Pong! (Took `{difference_ms}ms` to send.)')

    @commands.command(aliases=['reboot'])
    @commands.is_owner()
    async def restart(self, ctx):
        """ Reboots the bot. """
        logger.info('COMMENCING REBOOT')
        await ctx.message.add_reaction('\N{WAVING HAND SIGN}')
        os.execv(sys.executable, ['python'] + sys.argv)
        ctx.bot.logout()
        sys.exit(0)

    @commands.command(aliases=['die', 'getout', 'poweroff'])
    @commands.is_owner()
    async def shutdown(self, ctx):
        """ Turns off the bot. """
        logger.info('COMMENCING SHUTDOWN')
        await ctx.message.add_reaction('\N{WAVING HAND SIGN}')
        ctx.bot.logout()
        sys.exit(0)

    @commands.command()
    async def prefixes(self, ctx):
        """ Lists the bot's prefixes. """
        prefixes = ', '.join([f'`{p}`' for p in self.bot.command_prefix])
        await ctx.send(f'My prefixes are: {prefixes}')

    def _reload_ext(self, ext):
        self.bot.unload_extension(ext)
        self.bot.load_extension(ext)

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, ext: str):
        """ Reloads an extension. """
        try:
            if ext == 'all':
                names = ctx.bot.extensions.keys()
                logger.info('reloading %d extensions', len(names))
                for name in names:
                    self._reload_ext(name)
            else:
                logger.info('reloading %s', ext)
                self._reload_ext(f'dog.ext.{ext}')
        except:
            logger.exception(f'failed reloading extension {ext}')
            await ctx.message.add_reaction('\N{CROSS MARK}')
        else:
            await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')

    @commands.command(name='eval')
    @commands.is_owner()
    async def _eval(self, ctx, *, code: str):
        """ Evaluates a Python expression. """
        code_regex = re.compile(r'`(.+)`')
        match = code_regex.match(code)
        if match is None:
            logger.info('eval: tried to eval, no code (%s)', code)
            await ctx.send('No code was found. '
                           'Surround it in backticks (\\`code\\`), please!')
            return
        code = match.group(1)

        logger.info('eval: %s', code)

        env = {
            'bot': ctx.bot,
            'ctx': ctx,
            'msg': ctx.message,
            'guild': ctx.guild,
            'channel': ctx.channel,
            'me': ctx.message.author,

            'get': discord.utils.get,
            'find': discord.utils.find,

            '_': self.eval_last_result,
        }

        fmt_exception = '```py\n>>> {}\n\n{}: {}```'
        fmt_result = '```py\n>>> {}\n\n{}```'
        room = 2000 - (10 + len(code) + 6 + 3)

        env.update(globals())

        try:
            output = eval(code, env)

            if inspect.isawaitable(output):
                output = await output

            self.eval_last_result = output
            output = str(output)
        except Exception as e:
            name = type(e).__name__
            await ctx.send(fmt_exception.format(code, name, e))
            return

        if len(output) > room:
            logger.info('output too big, hasting')
            haste_url = await haste(output)
            await ctx.send(f'Full output: {haste_url}')
            output = output[:room] + '...'

        await ctx.send(fmt_result.format(code, output or 'None'))


def setup(bot):
    bot.add_cog(Admin(bot))
