import logging
import asyncpg

from discord.ext import commands
from dog import Cog

from .filter import CensorshipFilter
from .enums import CensorType, PunishmentType
from .filters import *

logger = logging.getLogger(__name__)


class Censorship(Cog):
    async def is_censoring(self, guild: discord.Guild, what: CensorType) -> bool:
        """Returns whether something is being censored for a guild."""
        if not await self.has_censorship_record(guild):
            return False
        sql = 'SELECT enabled FROM censorship WHERE guild_id = $1'
        async with self.bot.pgpool.acquire() as conn:
            enabled = (await conn.fetchrow(sql, guild.id))['enabled']
        return what.name in enabled

    async def has_censorship_record(self, guild: discord.Guild) -> bool:
        """Returns whether a censorship record is present for a guild."""
        sql = 'SELECT * FROM censorship WHERE guild_id = $1'
        async with self.bot.pgpool.acquire() as conn:
            return await conn.fetchrow(sql, guild.id) is not None

    async def censor(self, guild: discord.Guild, what: CensorType):
        """Censors something for a guild."""
        logger.info('Censoring %s for %s (%d)', what, guild.name, guild.id)
        async with self.bot.pgpool.acquire() as conn:
            if not await self.has_censorship_record(guild):
                logger.debug('Creating initial censorship data for guild %s (%d)', guild.name, guild.id)
                await conn.execute('INSERT INTO censorship VALUES ($1, \'{}\', \'{}\')', guild.id)
            await conn.execute('UPDATE censorship SET enabled = array_append(enabled, $1) '
                               'WHERE guild_id = $2', what.name, guild.id)

    async def delete_punishment(self, guild: discord.Guild, type: CensorType):
        """Deletes a punishment."""
        logger.debug('Removing punishment. gid=%d, censor=%s', guild.id, type)
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('DELETE FROM censorship_punishments WHERE guild_id = $1 AND censorship_type = $2',
                               guild.id, type.name)

    async def add_punishment(self, guild: discord.Guild, type: CensorType, punishment: PunishmentType):
        """Adds a punishment."""
        logger.debug('Adding punishment. gid=%d, censor=%s, punishment=%s', guild.id, type, punishment)
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('INSERT INTO censorship_punishments VALUES ($1, $2, $3)', guild.id, type.name,
                               punishment.name)

    async def get_punishment(self, guild: discord.Guild, type: CensorType) -> 'Union[PunishmentType, None]':
        """Returns a punishment for a censorship type."""
        logger.debug('Fetching punishment. gid=%d, censor=%s', guild.id, type)
        sql = 'SELECT punishment FROM censorship_punishments WHERE guild_id = $1 AND censorship_type = $2'
        async with self.bot.pgpool.acquire() as conn:
            row = await conn.fetchrow(sql, guild.id, type.name)
            return getattr(PunishmentType, row['punishment'], None) if row else None

    async def uncensor(self, guild: discord.Guild, what: CensorType):
        """Uncensors something for a guild."""
        if not await self.has_censorship_record(guild):
            return
        logging.info('Uncensoring %s for %s (%d)', what, guild.name, guild.id)
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('UPDATE censorship SET enabled = array_remove(enabled, $1) '
                               'WHERE guild_id = $2', what.name, guild.id)

    async def carry_out_punishment(self, censor_type: CensorType, msg: discord.Message):
        """Carries out a punishment."""
        punishment = await self.get_punishment(msg.guild, censor_type)
        if not punishment:
            logger.debug('Not carrying out punishment for %d, no punishment assigned to censor type %s.', msg.id,
                         censor_type)
            return
        logger.debug('Carrying out punishment. mid=%d aid=%d censor_type=%s punishment_type=%s', msg.id, msg.author.id,
                     censor_type, punishment)

        reason = f'(Automated) Censorship violation: {censor_type.name}'

        if punishment == PunishmentType.BAN:
            await msg.author.ban(reason=reason)
        elif punishment == PunishmentType.KICK:
            await msg.author.kick(reason=reason)

    @commands.group(aliases=['cs'])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def censorship(self, ctx):
        """
        Manages censorship. Censorship allows you to forbid certain types of messages in your
        server. If the modlog is setup, then Dogbot will post to the modlog whenever a message
        is censored.

        In order to censor, Dogbot needs to be able to delete messages. Ensure that Dogbot has
        proper permissions before enabling censoring. You may then disable and enable certain types of
        censorship with the `d?censorship censor` and `d?censorship uncensor` commands.

        You may manage certain roles from being censored with the `except`, `unexcept`, and
        `exceptions` subcommands. Note: The `except` and `unexcept` subcommands use role IDs, not
        role names or mentions. To list the roles (and their IDs) in this server, use `d?roles`.

        You must have the "Manage Server" permission in order to manage server censorship.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(
                f'You need to specify a valid subcommand to run. For help, run `{ctx.prefix}help cs`.'
            )

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
        await ctx.ok()

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
        await ctx.ok()

    @censorship.command(name='exceptions', aliases=['excepted'])
    async def _exceptions(self, ctx):
        """Lists the excepted roles, and their IDs."""
        roles = [(i, discord.utils.get(ctx.guild.roles, id=i)) for i in await self.get_guild_exceptions(ctx.guild)]

        if not roles:
            return await ctx.send('There are no roles being excepted.')

        def format_role(role_info):
            id, r = role_info
            return f'\N{BULLET} {r.name} ({r.id})' if r else f'\N{BULLET} <dead role> ({id})'

        code = '```\n' + '\n'.join(map(format_role, roles)) + '\n```'
        await ctx.send(code)

    @censorship.command(name='censor')
    async def _censor(self, ctx, censor_type: CensorType):
        """
        Censors a specific type of message.

        To view censor types, run d?cs list.
        """
        await self.censor(ctx.message.guild, censor_type)
        await ctx.ok()

    @censorship.command(name='list')
    async def _list(self, ctx):
        """Lists the censorship types."""
        types = ', '.join(f'`{t.name.lower()}`' for t in CensorType)
        wiki = 'https://github.com/slice/dogbot/wiki/Censorship'
        await ctx.send(f'Censorship types: {types}\n\nTo see what these do, click here: <{wiki}>')

    @censorship.command(name='censoring')
    async def _censoring(self, ctx, censor_type: CensorType = None):
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

        fmt_begin = f'Yes, ' if is_censoring else 'No, '
        fmt_status = 'not ' if not is_censoring else ''
        fmt = f'{fmt_begin} `{censor_type.name}` are {fmt_status}being censored.'
        await ctx.send(fmt)

    @censorship.command(name='uncensor')
    async def _uncensor(self, ctx, censor_type: CensorType):
        """
        Uncensors a specific type of message.

        To view censor types, run d?cs list.
        """
        await self.uncensor(ctx.message.guild, censor_type)
        await ctx.ok()

    @censorship.group(name='punish', aliases=['p'])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def censor_punish(self, ctx):
        """
        Manages censorship punishments. For each censorship type, you may assign a punishment
        to that type. The punishment will be carried out upon that specific censorship type being violated.

        Before using this, ensure that Dogbot can ban members and kick members. Excepted users are immune
        to being punished (and being censored in the first place). Only members with "Manage Server" can manage
        punishments.
        """
        if ctx.invoked_subcommand.qualified_name == 'censorship punish':
            await ctx.send(
                f'You need to specify a valid subcommand to run. For help, run `{ctx.prefix}help cs p`.'
            )

    @censor_punish.command(name='add')
    async def censor_punish_add(self, ctx, censor_type: CensorType, punishment: PunishmentType):
        """Adds a punishment."""
        if not await self.is_censoring(ctx.guild, censor_type):
            return await ctx.send(f'You aren\'t censoring `{censor_type.name.lower()}`, you should censor it first '
                                  f'with `d?cs censor {censor_type.name.lower()}`.')
        try:
            await self.add_punishment(ctx.guild, censor_type, punishment)
        except asyncpg.IntegrityConstraintViolationError:
            return await ctx.send('That censorship type already has a punishment!')
        await ctx.ok()

    @censor_punish.command(name='delete', aliases=['del', 'rm', 'remove'])
    async def censor_punish_delete(self, ctx, censor_type: CensorType):
        """Deletes a punishment."""
        await self.delete_punishment(ctx.guild, censor_type)
        await ctx.ok()

    @censor_punish.command(name='status')
    async def censor_punish_status(self, ctx):
        """
        Shows all punishments.

        This command will show all censorship filters that have a punishment assigned to them. It will show
        the censorship filter's name, and its punishment.
        """
        async with ctx.acquire() as conn:
            punishments = await conn.fetch('SELECT * FROM censorship_punishments WHERE guild_id = $1', ctx.guild.id)
            status = {r['censorship_type'].lower(): r['punishment'].lower() for r in punishments}
            await ctx.send(utils.format_dict(status))

    async def should_censor(self, msg: discord.Message, filter: CensorshipFilter) -> bool:
        """Returns whether a message should be censored based on a censorship filter and censor type."""
        return await self.is_censoring(msg.guild, filter.censor_type) and await filter().does_violate(msg)

    async def censor_message(self, msg: discord.Message, filter):
        """Censors a message, and posts to the modlog."""
        self.bot.dispatch('message_censor', filter, msg)
        try:
            await msg.delete()
        except discord.Forbidden:
            msg = "\N{CROSS MARK} I failed to censor that message because I couldn't delete it."
            await self.bot.send_modlog(msg.guild, msg)

    async def get_guild_exceptions(self, guild: discord.Guild):
        """Returns the list of exception role IDs that a guild has."""
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

        censors = (InviteCensorshipFilter, VideositeCensorshipFilter, ZalgoCensorshipFilter,
                   MediaLinksCensorshipFilter, ExecutableLinksCensorshipFilter, CapsCensorshipFilter,
                   CrashTextCensorshipFilter)

        # if the message author has a role that has been excepted, don't even check the message
        if any([role.id in await self.get_guild_exceptions(msg.guild) for role in msg.author.roles]):
            return

        # don't censor myself or other bots
        if msg.author == self.bot.user or msg.author.bot:
            return

        for censorship_filter in censors:
            if await self.should_censor(msg, censorship_filter):
                await self.censor_message(msg, censorship_filter)

                # punish the user
                try:
                    await self.carry_out_punishment(censorship_filter.censor_type, msg)
                except discord.Forbidden:
                    logger.warning('Unable to carry out punishment, forbidden! gid=%d', msg.guild.id)
                    pass
                break


def setup(bot):
    bot.add_cog(Censorship(bot))
