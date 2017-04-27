"""
Commands that are used to administrate the bot itself, not for your servers.
It also contains some utility commands that are used to check the health of the
bot, like d?ping.

Debugging commands like d?eval are also in this extension.
"""

import logging
import os
import subprocess
import sys
import textwrap
from time import monotonic

import discord
from discord.ext import commands

import dog_config as cfg
from dog import Cog

logger = logging.getLogger(__name__)


class Admin(Cog):
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
        logger.info('Update: Commencing reboot!')
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

    @commands.command(aliases=['poweroff', 'halt'])
    @commands.is_owner()
    async def shutdown(self, ctx):
        """ Turns off the bot. """
        logger.info('COMMENCING SHUTDOWN')
        await ctx.message.add_reaction('\N{WAVING HAND SIGN}')
        sys.exit(0)

    @commands.command()
    async def prefixes(self, ctx):
        """ Lists the bot's prefixes. """
        prefixes = ', '.join([f'`{p}`' for p in cfg.prefixes])
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
        }

        fmt_exception = '```py\n>>> {}\n\n{}: {}```'

        env.update(globals())

        indented_code = textwrap.indent(code, '    ')
        wrapped_code = 'async def _eval_code():\n' + indented_code

        try:
            exec(wrapped_code, env)
            return_value = await env['_eval_code']()

            if return_value is not None:
                await ctx.send(return_value)
        except Exception as e:
            name = type(e).__name__
            await ctx.send(fmt_exception.format(code, name, e))
            return


def setup(bot):
    bot.add_cog(Admin(bot))
