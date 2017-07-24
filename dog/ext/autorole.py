import logging
from enum import Enum, auto

import asyncpg
import discord
from discord.ext import commands
from dog import Cog
from dog.core import utils

log = logging.getLogger(__name__)


class AutoroleType(utils.EnumConverter, Enum):
    user = auto()
    bot = auto()


class Autorole(Cog):
    @commands.group(aliases=['ar'])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def autorole(self, ctx):
        """
        Manages autorole functionality.

        "Manage Roles" is required to manage roles. Keep in mind that Dogbot does not check the role hierarchy,
        meaning people who can autorole can elevate themselves to any role that Dogbot can add to someone, with abuse.

        All autoroles are logged in the mod log (if configured) when they happen. If assigning autoroles fails, ensure
        that the bot can add those roles, and that Dogbot's role is above them in the role hierarchy.

        Examples:
        d?autorole add user human
            Makes Dogbot give a role named "human" to every user who joins the server.
        d?ar add user human everyone
            Makes Dogbot give a role named "human" and "everyone" to every user who joins the server.
        d?ar add bot robot
            Makes Dogbot give a role named "robot" to every bot who gets added to the server.
        d?ar list
            Lists all autoroles in this server.
        d?ar delete bot
            Deletes the autoroles for bots.
        d?ar delete user
            Deletes the autoroles for users.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send('You must specify a subcommand to run. For help, run `d?help ar`.')

    async def assign_roles(self, type: str, member: discord.Member):
        async with self.bot.pgpool.acquire() as pg:
            # fetch autoroles for that user
            autorole = await pg.fetchrow('SELECT * FROM autoroles WHERE guild_id = $1 AND type = $2', member.guild.id,
                                         type)
            if not autorole:
                # log.debug('Ignoring autorole for guild %d -- no autorole for type "%s"!', member.guild.id, type)
                return []

            # get the role ids we need
            role_ids = autorole['roles']

            # collect roles to add
            roles_to_add = [discord.utils.get(member.guild.roles, id=role_id) for role_id in role_ids]

            # filter out dead roles
            roles_to_add = list(filter(lambda r: r is not None, roles_to_add))

            if not roles_to_add:
                # no roles to add
                return

            log.debug('Adding {} roles to {}.'.format(len(roles_to_add), member))

            try:
                # add roles
                await member.add_roles(*roles_to_add)
            except discord.Forbidden:
                log.warning('Failed to autorole %s. Forbidden!', member)
            else:
                return roles_to_add


    async def on_member_join(self, member: discord.Member):
        type = 'bot' if member.bot else 'user'

        # assign the roles
        roles_added = await self.assign_roles(type, member)

        if isinstance(roles_added, list) and len(roles_added) == 0:
            # no autoroles were added, don't log
            return

        # make embed
        mem = f'{member} (`{member.id}`)'
        fmt = (f'\N{BOOKMARK} Automatically assigned roles to {mem}' if isinstance(roles_added, list) else
               f'\N{CLOSED BOOK} Failed to automatically assign roles for {mem}')
        if roles_added:
            roles = ', '.join(map(lambda r: r.name, roles_added))
            fmt += f' - Added roles: {roles}'

        msg = self.bot.get_cog('Modlog').modlog_msg(fmt)

        # send to modlog
        await self.bot.send_modlog(member.guild, msg)


    @autorole.command()
    async def add(self, ctx, type: AutoroleType, *roles: discord.Role):
        """ Adds autoroles. """
        for role in roles:
            if role.position > ctx.guild.me.top_role.position:
                await ctx.send('I can\'t autorole the role \"{0.name}\". It\'s too high on the role list. Move my '
                               'role above it.'.format(role))
                return

        log.debug('Adding autorole. (type=%s, roles=%s)', type, roles)
        try:
            async with ctx.acquire() as conn:
                await conn.execute('INSERT INTO autoroles (guild_id, type, roles) VALUES ($1, $2, $3)', ctx.guild.id,
                                   type.name, list(map(lambda r: r.id, roles)))
        except asyncpg.UniqueViolationError:
            return await ctx.send('There\'s already autoroles for that type on this server.')
        await ctx.ok()

    @autorole.command()
    async def delete(self, ctx, type: AutoroleType):
        """ Deletes an autorole. """
        async with ctx.acquire() as conn:
            await conn.execute('DELETE FROM autoroles WHERE guild_id = $1 AND type = $2', ctx.guild.id, type.name)
        await ctx.ok()

    @autorole.command()
    async def list(self, ctx):
        """ Lists autoroles on this server. """
        def format_role(role_id):
            role = discord.utils.get(ctx.guild.roles, id=role_id)
            return role.name if role else '`<dead role>`'

        def format_record(record):
            formatted_roles = ', '.join([format_role(role_id) for role_id in record['roles']])
            return '{0[type]}: {1}'.format(record, formatted_roles)

        async with ctx.acquire() as conn:
            autoroles = await conn.fetch('SELECT * FROM autoroles WHERE guild_id = $1', ctx.guild.id)
        if not autoroles:
            return await ctx.send('There are no autoroles in this server.')
        await ctx.send('\n'.join([format_record(r) for r in autoroles]))


def setup(bot):
    bot.add_cog(Autorole(bot))
