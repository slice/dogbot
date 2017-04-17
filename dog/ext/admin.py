import textwrap
import subprocess
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

    def _restart(self):
        logger.info('reboot: executable=%s argv=%s', sys.executable, sys.argv)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @commands.command()
    @commands.is_owner()
    async def update(self, ctx):
        """ Updates dogbot from GitHub. """
        msg = await ctx.send('Fetching updates...')
        subprocess.check_output(['git', 'pull'])
        await msg.edit(content='Restarting...')
        logger.info('UPDATE: COMMENCING REBOOT!')
        self._restart()

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
        self._restart()

    @commands.command(aliases=['die', 'getout', 'poweroff'])
    @commands.is_owner()
    async def shutdown(self, ctx):
        """ Turns off the bot. """
        logger.info('COMMENCING SHUTDOWN')
        await ctx.message.add_reaction('\N{WAVING HAND SIGN}')
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

    @commands.command(name='eval', aliases=['exec'])
    @commands.is_owner()
    async def _eval(self, ctx, *, code: str):
        """ Executes Python code. """
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

        env.update(globals())

        wrapped_code = 'async def _eval_code():\n' + textwrap.indent(code, '    ')

        try:
            exec(wrapped_code, env)
            await env['_eval_code']()
        except Exception as e:
            name = type(e).__name__
            await ctx.send(fmt_exception.format(code, name, e))
            return


def setup(bot):
    bot.add_cog(Admin(bot))
