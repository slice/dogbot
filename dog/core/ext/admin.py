"""
Commands that are used to administrate and manage the bot itself.
"""
import logging
import os
import sys

import discord
from discord.ext.commands import command

from dog import Cog
from dog.core.checks import is_bot_admin
from dog.core.context import DogbotContext
from dog.core.converters import Image
from dog.core.utils import codeblock, shell

logger = logging.getLogger(__name__)


def restart_inplace():
    """Restarts the bot inplace."""
    logger.info('reboot: executable=%s argv=%s', sys.executable, sys.argv)
    os.execv(sys.executable, [sys.executable] + sys.argv)


async def sync_source_code():
    """Syncs my source code from remote."""

    # fetch bits from github
    await shell('git fetch --all')

    # forcibly reset our position to latest
    await shell('git reset --hard origin/master')


class Admin(Cog):
    @command(aliases=['sh', 'bash'])
    @is_bot_admin()
    async def shell(self, ctx: DogbotContext, *, cmd):
        """Executes a system command."""
        await ctx.send(codeblock(await shell(cmd)))

    @command()
    @is_bot_admin()
    async def hotpatch(self, ctx: DogbotContext):
        """Hotpatches Dogbot from Git."""
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

    @command()
    @is_bot_admin()
    async def update(self, ctx: DogbotContext):
        """Updates Dogbot from Git, then restarts."""
        msg = await ctx.send('\U000023f3 Pulling...')

        # update from github
        await sync_source_code()

        # restart
        await msg.edit(content='\N{WAVING HAND SIGN} Restarting, bye!')
        restart_inplace()

    @command()
    @is_bot_admin()
    async def set_avatar(self, ctx: DogbotContext, *, image_source: Image):
        """
        Sets the bot's avatar.

        If the bot is ratelimited, then it will wait.
        """
        async with self.bot.session.get(image_source) as resp:
            avatar_data = await resp.read()
            await self.bot.user.edit(avatar=avatar_data)
            await ctx.ok()

    @command()
    @is_bot_admin()
    async def set_username(self, ctx: DogbotContext, *, username):
        """Sets the bot's username."""
        try:
            await self.bot.user.edit(username=username)
        except discord.HTTPException as ex:
            await ctx.send(f'Failed! {ex}')
        else:
            await ctx.send('\N{OK HAND SIGN} Done.')

    @command(aliases=['reboot'])
    @is_bot_admin()
    async def restart(self, ctx: DogbotContext):
        """Reboots the bot."""
        logger.info('Commencing reboot!')
        await ctx.send('\N{WAVING HAND SIGN} Restarting, bye!')
        restart_inplace()

    @command(aliases=['poweroff', 'halt'])
    @is_bot_admin()
    async def shutdown(self, ctx: DogbotContext):
        """Turns off the bot."""
        if await ctx.confirm(title='Are you sure?', description="Are you sure you want to shut me down?"):
            logger.info('Commencing shutdown!')
            await ctx.send('\N{WAVING HAND SIGN} Bye!')
            sys.exit(0)

    @command()
    async def prefixes(self, ctx: DogbotContext):
        """Lists the bot's prefixes."""

        # global prefixes
        prefixes = ', '.join(f'"{p}"' for p in ctx.bot.cfg['bot']['prefixes'])

        msg = await ctx._('cmd.prefix.prefixes', prefixes=prefixes)

        # if we have supplemental prefixes, add them to the message
        suppl_prefixes = await ctx.bot.get_prefixes(ctx.guild)
        if suppl_prefixes:
            suppl_prefix_list = ', '.join(f'"{p}"' for p in suppl_prefixes)
            msg += '\n' + await ctx._('cmd.prefix.prefixes_guild', prefixes=suppl_prefix_list)

        await ctx.send(msg)

    @command()
    @is_bot_admin()
    async def reload(self, ctx: DogbotContext, ext=None):
        """ Reloads the bot/extensions of the bot. """
        try:
            if ext is None:
                self.bot.perform_full_reload()
            else:
                logger.info('Individual reload: %s', ext)
                self.bot.reload_extension(f'dog.ext.{ext}')
        except Exception:
            # perform_full_reload() handles exceptions for us
            if ext:
                logger.exception('Failed reloading extension: %s', ext)
            await ctx.message.add_reaction(ctx.tick('red', raw=True))
        else:
            await ctx.message.add_reaction(ctx.tick('green', raw=True))


def setup(bot):
    bot.add_cog(Admin(bot))
