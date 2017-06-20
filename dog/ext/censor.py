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
INVITE_RE = re.compile(r'(discordapp\.com/invite|discord\.gg)/([a-zA-Z_\-0-9]+)')
VIDEOSITE_RE = re.compile(r'(https?://)?(www\.)?(twitch\.tv|youtube\.com)/(.+)')


class CensorType(Enum):
    """ Signifies the type of censorship. """
    INVITES = 1
    VIDEOSITES = 2


class CensorTypeConverter(commands.Converter):
    async def convert(self, ctx, argument):
        censor_type = getattr(CensorType, argument.upper(), None)
        if not censor_type:
            raise commands.BadArgument('Invalid censorship type! Use `d?cs list` to view valid censorship types.')
        return censor_type


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
            await conn.execute('UPDATE censorship SET enabled = array_append(enabled, $1) '
                               'WHERE guild_id = $2', what.name, guild.id)

    async def enable_autoban(self, guild: discord.Guild):
        """ Enables autoban for a guild. """
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('INSERT INTO censorship_autoban VALUES ($1)', guild.id)

    async def disable_autoban(self, guild: discord.Guild):
        """ Disables autoban for a guild. """
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('DELETE FROM censorship_autoban WHERE guild_id = $1', guild.id)

    async def autoban_enabled(self, guild: discord.Guild) -> bool:
        """ Returns whether autoban is enabled for this guild. """
        async with self.bot.pgpool.acquire() as conn:
            return await conn.fetchrow('SELECT * FROM censorship_autoban WHERE guild_id = $1', guild.id) is not None

    async def uncensor(self, guild: discord.Guild, what: CensorType):
        """ Uncensors something for a guild. """
        if not await self.has_censorship_record(guild):
            return
        logging.info('Uncensoring %s for %s (%d)', what, guild.name, guild.id)
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('UPDATE censorship SET enabled = array_remove(enabled, $1) '
                               'WHERE guild_id = $2', what.name, guild.id)

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
            await conn.execute('UPDATE censorship SET exceptions = array_append(exceptions, $1) WHERE '
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
        roles = [(i, discord.utils.get(ctx.guild.roles, id=i)) for i in await self.get_guild_exceptions(ctx.guild)]

        if not roles:
            return await ctx.send('There are no roles being excepted.')

        def format_role(role_info):
            r, id = role_info
            return f'\N{BULLET} {r.name} ({r.id})' if r else f'\N{BULLET} <dead role> ({id})'

        code = '```\n' + '\n'.join(map(format_role, roles)) + '\n```'
        await ctx.send(code)

    @censorship.command(name='censor')
    async def _censor(self, ctx, censor_type: CensorTypeConverter):
        """
        Censors a specific type of message.

        To view censor types, run d?cs list.
        """
        await self.censor(ctx.message.guild, censor_type)
        await self.bot.ok(ctx)

    @censorship.command(name='list')
    async def _list(self, ctx):
        """ Lists the censorship types. """
        types = ', '.join([f'`{t.name.lower()}`' for t in CensorType])
        wiki = 'https://github.com/sliceofcode/dogbot/wiki/Censorship'
        await ctx.send(f'Censorship types: {types}\n\nTo see what these do, click here: <{wiki}>')

    @censorship.command(name='censoring')
    async def _censoring(self, ctx, censor_type: CensorTypeConverter = None):
        """
        Views what types of messages are being censored.

        If you pass the name of a censor type (view all censor types with d?cs list) into the
        command, Dogbot will tell if you if that certain censor type is enabled or not.
        """

        if not censor_type:
            censor_types = [t.name for t in CensorType]
            censoring_dict = {name.lower(): await self.is_censoring(ctx.guild, getattr(CensorType, name))
                              for name in censor_types}
            await ctx.send(utils.format_dict(censoring_dict))
            return

        is_censoring = await self.is_censoring(ctx.guild, censor_type)

        await ctx.send((f'Yes, ' if is_censoring else 'No, ') + f'`{what}` are ' + ('not ' if not is_censoring else '')
                       + 'being censored.')

    @censorship.command(name='uncensor')
    async def _uncensor(self, ctx, censor_type: CensorTypeConverter):
        """
        Uncensors a specific type of message.

        To view censor types, run d?cs list.
        """
        await self.uncensor(ctx.message.guild, censor_type)
        await self.bot.ok(ctx)

    @censorship.group(name='autoban')
    async def _autoban(self, ctx):
        """
        Manages censorship autobanning. When enabled, Dogbot will ban anyone that violates
        the censorship filter. Dogbot attaches a reason to every ban.

        Before using this, ensure that Dogbot can ban members.
        """

    @_autoban.command(name='enable')
    async def _autoban_enable(self, ctx):
        """ Enables autobanning. """
        await self.enable_autoban(ctx.guild)
        await ctx.bot.ok(ctx)

    @_autoban.command(name='disable')
    async def _autoban_disable(self, ctx):
        """ Disables autobanning. """
        await self.disable_autoban(ctx.guild)
        await ctx.bot.ok(ctx)

    @_autoban.command(name='status')
    async def _autoban_status(self, ctx):
        """ Is autobanning enabled? """
        is_enabled = await self.autoban_enabled(ctx.guild)
        await ctx.send('**Yup!** Autobanning is enabled.' if is_enabled else '**Nope!** Autobanning is disabled.')

    async def should_censor(self, msg: discord.Message, censor_type: CensorType, regex) -> bool:
        """ Returns whether a message should be censored based on a regex and censor type. """
        return await self.is_censoring(msg.guild, censor_type) and regex.search(msg.content) \
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
            record = await conn.fetchrow(sql, guild.id)
            return record['exceptions'] if record else []

    async def on_message(self, msg: discord.Message):
        if not isinstance(msg.channel, discord.abc.GuildChannel) or isinstance(msg.author, discord.User):
            # no dms
            return
        
        if not await self.has_censorship_record(msg.guild):
            # no censorship record yet!
            return

        censors = [
            (CensorType.INVITES, INVITE_RE, '\u002a\u20e3 Invite-containing message censored'),
            (CensorType.VIDEOSITES, VIDEOSITE_RE, '\u002a\u20e3 Videosite-containing message censored')
        ]

        # if the message author has a role that has been excepted, don't even check the message
        if any([role.id in await self.get_guild_exceptions(msg.guild) for role in msg.author.roles]):
            return

        for censor_type, regex, title in censors:
            if await self.should_censor(msg, censor_type, regex):
                await self.censor_message(msg, title)

                # automatically ban the user, if applicable
                if await self.autoban_enabled(msg.guild):
                    try:
                        logger.debug('Autobanning %d', msg.author.id)
                        await msg.author.ban(reason=f'Violated censorship filter \N{EM DASH} {censor_type.name.lower()}')
                    except discord.Forbidden:
                        pass
                break


def setup(bot):
    bot.add_cog(Censorship(bot))
