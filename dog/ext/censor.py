"""
Contains censorship functionality.
"""

import logging
import re
from enum import Enum

import discord
from discord.ext import commands

from dog import Cog
from dog.core import utils

logger = logging.getLogger(__name__)
INVITE_RE = re.compile(r'(discordapp\.com\/invite|discord\.gg)\/([a-zA-Z_\-0-9]+)')
VIDEOSITE_RE = re.compile(r'(https?:\/\/)?(www\.)?(twitch\.tv|youtube\.com)\/(.+)')


class CensorType(Enum):
    """ Signifies the type of censorship. """
    INVITES = 1
    VIDEOSITES = 2


class Censorship(Cog):
    async def is_censoring(self, guild: discord.Guild, what: CensorType) -> bool:
        """ Returns whether something is being censored for a guild. """
        if not await self.has_censorship_record(guild):
            return False
        sql = 'SELECT enabled FROM censorship WHERE guild_id = $1'
        async with self.bot.pgpool.acquire() as conn:
            enabled = (await conn.fetchrow(sql, guild.id))['enabled']
        return what.name in enabled
    
    async def has_censorship_record(self, guild: discord.Guild) -> bool:
        """ Returns whether a censorship record is present for a guild. """
        sql = 'SELECT * FROM censorship WHERE guild_id = $1'
        async with self.bot.pgpool.acquire() as conn:
            return await conn.fetchrow(sql, guild.id) is not None

    async def censor(self, guild: discord.Guild, what: CensorType):
        """ Censors something for a guild. """
        logger.info('Censoring %s for %s (%d)', what, guild.name, guild.id)
        async with self.bot.pgpool.acquire() as conn:
            if not await self.has_censorship_record(guild):
                logger.debug('Creating initial censorship data for guild %s (%d)', guild.name, guild.id)
                await conn.execute('INSERT INTO censorship VALUES ($1, \'{}\', \'{}\')', guild.id)
            # TODO: don't concat the string directly
            await conn.execute(f'UPDATE censorship SET enabled = enabled || \'{{"{what.name}"}}\' '
                               'WHERE guild_id = $1', guild.id)

    async def uncensor(self, guild: discord.Guild, what: CensorType):
        """ Uncensors something for a guild. """
        if not await self.has_censorship_record(guild):
            return
        logging.info('Uncensoring %s for %s (%d)', what, guild.name, guild.id)
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute(f'UPDATE censorship SET enabled = array_remove(enabled, \'{what.name}\') '
                               'WHERE guild_id = $1', guild.id)

    @commands.command()
    async def roles(self, ctx):
        """ Views the roles (and their IDs) in this server. """
        code = '```\n' + '\n'.join([f'\N{BULLET} {r.name} ({r.id})' for r in ctx.guild.roles]) + '\n```'
        try:
            await ctx.send(code)
        except discord.HTTPException:
            await ctx.send(f'You have too many roles ({len(ctx.guild.roles)}) for me to list!')

    @commands.group(aliases=['cs'])
    @commands.has_permissions(manage_guild=True)
    async def censorship(self, ctx):
        """
        Manages censorship. Censorship allows you to forbid certain types of messages in your
        server. If the modlog is setup, then Dogbot will post to the modlog whenever a message
        is censored.

        In order to censor, Dogbot needs to be able to delete messages. Ensure that Dogbot has
        proper permissions before enabling censoring. You can list the types of censorship
        with the `d?censorship list` subcommand. You may then disable and enable certain types of
        censorship with the `d?censorship censor` and `d?censorship uncensor` commands.

        You may manage certain roles from being censored with the `except`, `unexcept`, and
        `exceptions` subcommands. Note: The `except` and `unexcept` subcommands use role IDs, not
        role names or mentions. To list the roles (and their IDs) in this server, use `d?roles`.

        You must have the "Manage Server" permission in order to manage server censorship.
        """
        pass

    @censorship.command(name='except')
    async def _except(self, ctx, role_id: int):
        """
        Excepts a role from being censored.

        This command only accepts role IDs. In order to view the list of roles and their IDs, use
        d?roles.
        """
        if not discord.utils.get(ctx.guild.roles, id=role_id):
            return await ctx.send('I couldn\'t find a role with that ID. To view the list of roles '
                                  '(and their IDs) in this server, use the `d?roles` command.'
                                  ' **Note:** This command only takes role IDs, not role names or '
                                  'mentions.')
        if not await self.has_censorship_record(ctx.guild):
            return await ctx.send('You need to censor something first before you can except.')
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('UPDATE censorship SET exceptions = exceptions || $1 WHERE '
                               'guild_id = $2', role_id, ctx.guild.id)
        await self.bot.ok(ctx)

    @censorship.command(name='unexcept')
    async def _unexcept(self, ctx, role_id: int):
        """
        Unexcepts a role from being censored.

        This command only accepts role IDs. In order to view the list of roles and their IDs, use
        d?roles.
        """
        sql = 'UPDATE censorship SET exceptions = array_remove(exceptions, $1) WHERE guild_id = $2'
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute(sql, role_id, ctx.guild.id)
        await self.bot.ok(ctx)

    @censorship.command(name='exceptions', aliases=['excepted'])
    async def _exceptions(self, ctx):
        """ Lists the excepted roles, and their IDs. """
        roles = [discord.utils.get(ctx.guild.roles, id=i) for i in await self.get_guild_exceptions(ctx.guild)]

        if not roles:
            return await ctx.send('There are no roles being excepted.')

        code = '```\n' + '\n'.join([f'\N{BULLET} {r.name} ({r.id})' for r in roles]) + '\n```'
        await ctx.send(code)

    @censorship.command(name='censor')
    async def _censor(self, ctx, what: str):
        """ Censors a specific type of message. """
        censor_type = getattr(CensorType, what.upper(), None)
        if not censor_type:
            return await ctx.send('Invalid censorship type.')
        await self.censor(ctx.message.guild, censor_type)
        await self.bot.ok(ctx)

    @censorship.command(name='list')
    async def _list(self, ctx):
        """ Lists the censorship types. """
        types = ', '.join([f'`{t.name.lower()}`' for t in CensorType])
        await ctx.send(f'Censorship types: {types}')

    @censorship.command(name='censoring')
    async def _censoring(self, ctx, what: str = None):
        """
        Views what types of messages are being censored.

        If you pass the name of a censor type (view all censor types with d?cs list) into the
        command, Dogbot will tell if you if that certain censor type is enabled or not.
        """

        if not what:
            censor_types = [t.name for t in CensorType]
            censoring_dict = {name.lower(): await self.is_censoring(ctx.guild,
                                                                    getattr(CensorType, name))
                              for name in censor_types}
            await ctx.send(utils.format_dict(censoring_dict))
            return

        censor_type = getattr(CensorType, what.upper(), None)
        if not censor_type:
            return await ctx.send('Invalid censorship type.')
        is_censoring = await self.is_censoring(ctx.guild, censor_type)

        if is_censoring:
            await ctx.send(f'Yes, `{what}` are being censored.')
        else:
            await ctx.send(f'No, `{what}` are not being censored.')

    @censorship.command(name='uncensor')
    async def _uncensor(self, ctx, what: str):
        """ Uncensors a specific type of message. """
        censor_type = getattr(CensorType, what.upper(), None)
        if not censor_type:
            return await ctx.send('Invalid censorship type.')
        await self.uncensor(ctx.message.guild, censor_type)
        await self.bot.ok(ctx)

    async def should_censor(self, msg: discord.Message, censor_type: CensorType, regex) -> bool:
        """ Returns whether a message should be censored based on a regex and censor type. """
        return await self.is_censoring(msg.guild, censor_type) and regex.match(msg.content) \
            is not None

    async def censor_message(self, msg: discord.Message, title: str):
        """ Censors a message, and posts to the modlog. """
        try:
            await msg.delete()
        except discord.Forbidden:
            await self.bot.send_modlog(msg.guild, ':x: I failed to censor a message because '
                                       'I couldn\'t delete it! Please fix my permissions.')
        else:
            embed = self.bot.get_cog('Modlog')._make_message_embed(msg, title=title)
            await self.bot.send_modlog(msg.guild, embed=embed)

    async def get_guild_exceptions(self, guild: discord.Guild):
        """ Returns the list of exception role IDs that a guild has. """
        sql = 'SELECT exceptions FROM censorship WHERE guild_id = $1'
        async with self.bot.pgpool.acquire() as conn:
            return await conn.fetch(sql, guild.id)

    async def on_message(self, msg: discord.Message):
        if not isinstance(msg.channel, discord.TextChannel) or isinstance(msg.author, discord.User):
            return
        
        if not await self.has_censorship_record(msg.guild):
            return

        censors = [
            (CensorType.INVITES, INVITE_RE, '\u002a\u20e3 Invite-containing message censored'),
            (CensorType.VIDEOSITES, VIDEOSITE_RE, '\u002a\u20e3 Videosite-containing message censored')
        ]

        if any([role.id in await self.get_guild_exceptions(msg.guild) for role in msg.author.roles]):
            return

        for censor_type, regex, title in censors:
            if await self.should_censor(msg, censor_type, regex):
                await self.censor_message(msg, title)
                break


def setup(bot):
    bot.add_cog(Censorship(bot))
