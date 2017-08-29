"""
Commands that are used to administrate the bot itself.
It also contains some utility commands that are used to check the health of the
bot, like d?ping.
"""
import logging
import os
import sys
from time import monotonic

from discord.ext import commands

from dog import Cog
from dog.core import converters
from dog.core.utils import codeblock
from dog.core.utils.system import shell

logger = logging.getLogger(__name__)


def _restart():
    logger.info('reboot: executable=%s argv=%s', sys.executable, sys.argv)
    os.execv(sys.executable, [sys.executable] + sys.argv)


class Admin(Cog):

    @commands.command(aliases=['sh', 'bash'])
    @commands.is_owner()
    async def shell(self, ctx, *, cmd):
        """ Executes a system command. """
        await ctx.send(codeblock(await shell(cmd)))

    @commands.command(aliases=['update'])
    @commands.is_owner()
    async def hotpatch(self, ctx):
        """ Hotpatches Dogbot from GitHub. """
        msg = await ctx.send('\U000023f3 Pulling...')

        # update from github
        await shell('git fetch --all')
        await shell('git reset --hard origin/master')

        await msg.edit(content='\U000023f3 Reloading extensions...')
        try:
            ctx.bot.reload_all_extensions()
        except Exception:
            await msg.edit(content=f'{ctx.red_tick} An error has occurred.')
            logger.exception('Hotpatch error')
        else:
            await msg.edit(content=f'{ctx.green_tick} Hotpatch successful.')


    @commands.command()
    @commands.is_owner()
    async def set_avatar(self, ctx, *, image_source: converters.Image):
        """ Sets the bot's avatar. """
        async with self.bot.session.get(image_source) as resp:
            avatar_data = await resp.read()
            await self.bot.user.edit(avatar=avatar_data)
            await ctx.ok()

    @commands.command(aliases=['reboot'])
    @commands.is_owner()
    async def restart(self, ctx):
        """ Reboots the bot. """
        logger.info('COMMENCING REBOOT')
        await ctx.message.add_reaction('\N{WAVING HAND SIGN}')
        _restart()

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

        # global prefixes
        prefixes = ', '.join(f'`{p}`' for p in ctx.bot.cfg['bot']['prefixes'])

        msg = await ctx._('cmd.prefix.prefixes', prefixes=prefixes)

        # if this guild is in the prefix cache, tack on the guild's additional prefixes too
        if ctx.guild.id in ctx.bot.prefix_cache:
            suppl_prefixes = ctx.bot.prefix_cache[ctx.guild.id]
            if suppl_prefixes:
                suppl_prefix_list = ', '.join(f'`{p}`' for p in suppl_prefixes)
                msg += '\n' + await ctx._('cmd.prefix.prefixes_guild', prefixes=suppl_prefix_list)

        await ctx.send(msg)

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, ext: str = None):
        """ Reloads the bot/extensions of the bot. """
        try:
            if ext is None:
                self.bot.perform_full_reload()
            else:
                logger.info('Individual reload: %s', ext)
                self.bot.reload_extension(f'dog.ext.{ext}')
        except:
            # perform_full_reload() handles exceptions for us
            if ext:
                logger.exception('Failed reloading extension: %s', ext)
            await ctx.message.add_reaction(ctx.tick('red', raw=True))
        else:
            await ctx.message.add_reaction(ctx.tick('green', raw=True))


def setup(bot):
    bot.add_cog(Admin(bot))
