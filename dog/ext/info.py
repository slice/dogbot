"""
Information extension.
"""
import logging

import discord
from discord.ext import commands

from dog import Cog
from dog.core import utils, checks, converters


def cm(v):
    return utils.commas(v)


SERVER_INFO_MEMBERS = '''{} total member(s)
{} online, {} offline, {}% online
{} human(s), {} bot(s), ratio: {}
'''

SERVER_INFO_COUNT = '''{0} role(s)
{3} channel(s), {1} text, {2} voice'''

logger = logging.getLogger(__name__)


class Info(Cog):
    @commands.command(aliases=['perms'])
    @commands.guild_only()
    async def permissions(self, ctx):
        """
        Views my permissions in this server.

        This does not view my permissions in this channel. In other words,
        channel permission overwrites are not taken into account here.
        """
        perms = ctx.guild.me.guild_permissions

        paginator = commands.Paginator()

        max_perm_length = max(len(checks.beautify_permission_name(p[0])) for p in perms)

        for attr, value in perms:
            indicator = '\U00002705' if value else '\U0000274c'
            paginator.add_line(f'{checks.beautify_permission_name(attr): <{max_perm_length}} {indicator}')

        for page in paginator.pages:
            await ctx.send(page)

    @commands.group(aliases=['user'], invoke_without_command=True)
    @commands.guild_only()
    async def profile(self, ctx, *, who: converters.RawUser = None):
        """ Shows information about a user. """
        who = who or ctx.author

        embed = discord.Embed(title=f'{who} \N{EM DASH} {who.id}' + (' <:bot:349717107124207617>' if who.bot else ''))
        embed.set_thumbnail(url=who.avatar_url)

        # shared servers
        shared_servers = sum(1 for g in ctx.bot.guilds if who in g.members)
        embed.add_field(name='Shared Servers', value=shared_servers)

        # supporter stuff <3
        if checks.is_supporter(ctx.bot, who):
            async with ctx.acquire() as conn:
                desc = await conn.fetchrow('SELECT * FROM profile_descriptions WHERE id = $1', who.id)
                if desc:
                    embed.color = discord.Color(desc['color'])
                    embed.add_field(name='Profile Description', value=desc['description'])

        # shortcut for adding a field with ago and absolute datetime info
        def add_joined_field(*, attr, name, **kwargs):
            dt = getattr(who, attr)
            embed.add_field(name=name, value=f'{utils.ago(dt)}\n{utils.standard_datetime(dt)} UTC', **kwargs)
        add_joined_field(attr='created_at', name='Created' if who.bot else 'Joined Discord', inline=False)

        # if this is a member, show extended information
        if isinstance(who, discord.Member):
            add_joined_field(attr='joined_at', name='Joined this Server', inline=False)
            roles = ', '.join(r.name for r in sorted(who.roles, key=lambda r: r.position, reverse=True)
                              if r != ctx.guild.default_role)
            embed.add_field(name='Roles', value=roles)
        else:
            # not in server, make sure to note that
            embed.description = "**NOTE:** This user is not in this server."

        # show some mod-related stuff for mods
        if checks.member_is_moderator(ctx.author):
            try:
                # is this person banned?
                entry = discord.utils.find(lambda ban_entry: ban_entry.user == who, await ctx.guild.bans())
                if entry:
                    embed.color = discord.Color.red()
                    reason = f'Reason: {entry.reason}' if entry.reason else 'No reason was provided.'
                    embed.add_field(name='Banned', value=f'**This user has been banned.** {reason}')
            except (discord.HTTPException, discord.Forbidden):
                # ignore permission/http errors
                pass

        await ctx.send(embed=embed)

    @profile.command(name='describe')
    @checks.is_supporter_check()
    async def profile_describe(self, ctx, color: discord.Color, *, description):
        """ Sets your profile description and color. Supporter only. """
        if len(description) > 1024:
            return await ctx.send('That description is too long. There is a maximum of 1024 characters.')
        async with ctx.acquire() as conn:
            sql = """INSERT INTO profile_descriptions (id, description, color) VALUES ($1, $2, $3)
                     ON CONFLICT (id) DO UPDATE SET description = $2, color = $3"""
            await conn.execute(sql, ctx.author.id, description, color.value)
        await ctx.send('\N{OK HAND SIGN} Updated your profile!')

    @commands.command(aliases=['guild'])
    @commands.guild_only()
    async def server(self, ctx):
        """ Shows information about the server. """
        g = ctx.guild
        embed = discord.Embed(title=f'{g.name} \N{EM DASH} {g.id}')

        # server icon
        if g.icon_url:
            embed.set_thumbnail(url=g.icon_url)

        # members
        humans, bots = 0, 0

        for member in g.members:
            if member.bot:
                bots += 1
            else:
                humans += 1

        total_members = len(g.members)
        num_online = len(list(filter(lambda m: m.status is discord.Status.online, g.members)))
        num_offline = len(list(filter(lambda m: m.status is discord.Status.offline, g.members)))
        embed.add_field(name='Members', value=SERVER_INFO_MEMBERS.format(
            cm(total_members), cm(num_online), cm(num_offline),
            round((num_online / total_members) * 100, 2),
            humans, bots, round(humans / bots, 2)
        ))

        embed.add_field(name='Count', value=SERVER_INFO_COUNT.format(
            cm(len(g.roles)), cm(len(g.text_channels)), cm(len(g.voice_channels)),
            cm(len(g.channels))
        ))

        created = f'Created: {g.created_at} UTC\n{utils.ago(g.created_at)}'
        embed.add_field(name='Created', value=created)

        # guild owner
        embed.set_footer(text=f'Owned by {g.owner}', icon_url=g.owner.avatar_url)

        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def roles(self, ctx):
        """
        Views detailed information about the roles in this server.

        Information is presented in a table-like layout.

        Columns:
            - Role position
                The role's position in the hierarchy. The bottom role is #0.
            - Role name
            - Role color
            - Role ID
            - Role properties
            - Role members

        Role properties:
            Role properties are represented as a sequence of characters.
            Each character has a separate meaning.

            H: This role is hoisted.
            M: This role is managed.
            @: This role is mentionable by everyone.
            D: This role is the default role (@everyone).
            A: This role has the "Administrator" permission.
            E: This role has the "Mention Everyone" permission.
        """
        paginator = commands.Paginator()

        sorted_roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
        longest_role_name = max(map(lambda r: len(r.name), ctx.guild.roles))

        # add lines
        for role in sorted_roles:
            # compile a list of role properties
            attrs = {
                # role attributes
                'H': role.hoist, 'M': role.managed, '@': role.mentionable, 'D': role.is_default(),

                # role permissions
                'A': role.permissions.administrator, 'E': role.permissions.mention_everyone
            }
            properties = ''.join(rep for rep, val in attrs.items() if val)

            # how many members?
            members = utils.commas(len(role.members))

            # get color
            color = 'default' if role.color == discord.Color.default() else str(role.color)

            fmt = (f'{role.position: <2} {role.name: <{longest_role_name}} {color} {role.id: <18} '
                   f'{properties: <{len(attrs)}} {members: <4}')
            paginator.add_line(fmt)

        for page in paginator.pages:
            await ctx.send(page)

    def _make_joined_embed(self, member):
        embed = utils.make_profile_embed(member)
        joined_dif = utils.ago(member.created_at)
        embed.add_field(name='Joined Discord',
                        value=f'{joined_dif}\n{utils.standard_datetime(member.created_at)} UTC')
        return embed

    @commands.command()
    @commands.guild_only()
    async def joined(self, ctx, target: discord.Member=None):
        """
        Shows when someone joined this server and Discord.

        If no arguments were passed, your information is shown.
        """
        if target is None:
            target = ctx.message.author

        embed = self._make_joined_embed(target)
        joined_dif = utils.ago(target.joined_at)
        embed.add_field(name='Joined this Server',
                        value=f'{joined_dif}\n{utils.standard_datetime(target.joined_at)} UTC',
                        inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def earliest(self, ctx):
        """ Shows who in this server had the earliest Discord join time. """
        members = {m: m.created_at for m in ctx.guild.members if not m.bot}
        earliest_time = min(members.values())
        for member, time in members.items():
            if earliest_time == time:
                await ctx.send(embed=self._make_joined_embed(member))


def setup(bot):
    bot.add_cog(Info(bot))
