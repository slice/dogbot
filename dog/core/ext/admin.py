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
from time import monotonic

import discord
from discord.ext import commands

import dog_config as cfg
from dog.core import botcollection, checks, utils
from dog import Cog
from dog.haste import haste

logger = logging.getLogger(__name__)


def _restart():
    logger.info('reboot: executable=%s argv=%s', sys.executable, sys.argv)
    os.execv(sys.executable, [sys.executable] + sys.argv)


class Admin(Cog):
    @commands.command()
    @commands.is_owner()
    @checks.bot_only()
    async def leave_collections(self, ctx):
        """ Leaves collections. """
        left_guilds = []
        for g in ctx.bot.guilds:
            if await botcollection.is_bot_collection(ctx.bot, g):
                ratio = botcollection.user_to_bot_ratio(g)
                left_guilds.append(f'\N{BULLET} {g.name} (`{g.id}`, ratio=`{ratio}`)')
                await ctx.bot.notify_think_is_collection(g)
                await g.leave()
        if not left_guilds:
            return await ctx.send('\N{SMIRKING FACE} No collections!')
        await ctx.send('\n'.join(left_guilds))
        await ctx.send(f'Left `{len(left_guilds)}` guilds in total.')

    @commands.command()
    @commands.is_owner()
    @checks.bot_only()
    async def rotate_game(self, ctx):
        """ Immediately rotates the bot's playing status. """
        await ctx.bot.rotate_game()
        await ctx.ok()

    @commands.command()
    @commands.is_owner()
    async def update(self, ctx, is_hot: str = None):
        """ Updates dogbot from GitHub. """
        msg = await ctx.send('Fetching updates...')

        # update from github
        subprocess.check_output(['git', 'fetch', '--all'])
        subprocess.check_output(['git', 'reset', '--hard', 'origin/master'])

        if is_hot is not None:
            await msg.edit(content='Reloading extensions...')
            try:
                self.bot.reload_all_extensions()
            except Exception as e:
                await msg.edit(content='An error has occurred.')
                logger.exception('Failed to hotpatch')
            else:
                await msg.edit(content='Hotpatch successful.')
        else:
            await msg.edit(content='Restarting...')
            logger.info('Update: Commencing reboot!')
            _restart()

    @commands.command()
    async def ping(self, ctx):
        """ You know what this does. """

        # get ws ping
        begin_ws = monotonic()
        await (await ctx.bot.ws.ping())
        end_ws = monotonic()

        # get rtt
        begin = monotonic()
        msg = await ctx.send('Pong!')
        end = monotonic()

        rtt = round((end - begin) * 1000, 2)
        ws = round((end_ws - begin_ws) * 1000, 2)

        await msg.edit(content=f'Pong! \N{EM DASH} WS: `{ws}ms`, RTT: `{rtt}ms`')

    @commands.command()
    @commands.is_owner()
    async def set_avatar(self, ctx, *, url: str):
        """ Sets the bot's avatar. """
        async with self.bot.session.get(url) as resp:
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
    @checks.bot_only()
    async def prefixes(self, ctx):
        """ Lists the bot's prefixes. """
        prefixes = ', '.join([f'`{p}`' for p in cfg.prefixes])
        await ctx.send(f'My prefixes are: {prefixes}')

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
            await ctx.message.add_reaction('\N{CROSS MARK}')
        else:
            await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')

    @commands.command()
    @commands.is_owner()
    async def sql(self, ctx, *, query: str):
        """ Executes SQL queries. """
        # ew i know
        sql = subprocess.run(['psql', '-U', 'postgres', '-d', ctx.bot.database, '-c', query], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        if sql.stderr != b'':
            return await ctx.send('Something went wrong!\n```{}\n```'.format(sql.stderr.decode()))
        if len(sql.stdout) > 1992:
            await ctx.send(await haste(self.bot.session, sql.stdout.decode()))
        else:
            await ctx.send('```\n{}\n```'.format(utils.prevent_codeblock_breakout(sql.stdout.decode())))


def setup(bot):
    bot.add_cog(Admin(bot))
