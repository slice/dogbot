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


def restart_inplace():
    """ Restarts the bot inplace. """
    logger.info('reboot: executable=%s argv=%s', sys.executable, sys.argv)
    os.execv(sys.executable, [sys.executable] + sys.argv)


async def sync_source_code():
    """ Syncs my source code from remote. """

    # fetch bits from github
    await shell('git fetch --all')

    # forcibly reset our position to latest
    await shell('git reset --hard origin/master')


class Admin(Cog):
    @commands.command(aliases=['sh', 'bash'])
    @commands.is_owner()
    async def shell(self, ctx, *, cmd):
        """ Executes a system command. """
        await ctx.send(codeblock(await shell(cmd)))

    @commands.command()
    @commands.is_owner()
    async def hotpatch(self, ctx):
        """ Hotpatches Dogbot from Git. """
        msg = await ctx.send('\U000023f3 Pulling...')

        # update from github
        await sync_source_code()

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
    async def update(self, ctx):
        """ Updates Dogbot from Git, then restarts. """
        msg = await ctx.send('\U000023f3 Pulling...')

        # update from github
        await sync_source_code()

        # restart
        await msg.edit(content='\N{WAVING HAND SIGN} Restarting, bye!')
        restart_inplace()

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
        logger.info('Commencing reboot!')
        await ctx.send('\N{WAVING HAND SIGN} Restarting, bye!')
        restart_inplace()

    @commands.command(aliases=['poweroff', 'halt'])
    @commands.is_owner()
    async def shutdown(self, ctx):
        """ Turns off the bot. """
        if await ctx.confirm(title='Are you sure?', description="Are you sure you want to me down?"):
            logger.info('Commencing shutdown!')
            await ctx.send('\N{WAVING HAND SIGN} Bye!')
            sys.exit(0)

    @commands.command()
    async def prefixes(self, ctx):
        """ Lists the bot's prefixes. """

        # global prefixes
        prefixes = ', '.join(f'`{p}`' for p in ctx.bot.cfg['bot']['prefixes'])

        msg = await ctx._('cmd.prefix.prefixes', prefixes=prefixes)

        # if we have supplemental prefixes, add them to the message
        suppl_prefixes = ctx.bot.prefix_cache.get(ctx.guild.id)
        if suppl_prefixes:
            suppl_prefix_list = ', '.join(f'`{p}`' for p in suppl_prefixes)
            msg += '\n' + await ctx._('cmd.prefix.prefixes_guild', prefixes=suppl_prefix_list)

        await ctx.send(msg)

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, ext=None):
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
