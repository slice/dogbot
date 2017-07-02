"""
Contains commands that relate to server moderation and management.
"""

import logging

import discord
from discord.ext import commands

from dog import Cog
from dog.core import checks, utils, converters

logger = logging.getLogger(__name__)


class Mod(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mute_tasks = {}

    async def __global_check(self, ctx: commands.Context):
        # do not handle guild-specific command disables in dms
        if not isinstance(ctx.channel, discord.abc.GuildChannel):
            return True

        banned_names = [
            'Can\'t Use Dog', 'can\'t use dog', 'Dog Plonk', 'dog plonk',
            'Banned from Dog', 'banned from dog'
        ]

        if any([discord.utils.get(ctx.author.roles, name=name) for name in banned_names]):
            return False

        return not await self.bot.command_is_disabled(ctx.guild, ctx.command.name)

    async def on_message(self, message: discord.Message):
        # do not handle invisibility in dms
        if isinstance(message.channel, discord.abc.PrivateChannel):
            return

        if await self.bot.config_is_set(message.guild, 'invisible_announce'):
            if message.author.status is discord.Status.offline:
                reply = 'Hey {0.mention}! You\'re invisible. Stop being invisible, please. Thanks.'
                await message.channel.send(reply.format(message.author))

    async def base_purge(self, ctx: commands.Context, limit: int, check=None, **kwargs):
        # check if it's too much
        if limit > 1000:
            await ctx.send('Too many messages to purge. 1,000 is the maximum.')
            return

        # purge the actual command message too
        limit += 1

        try:
            msgs = await ctx.channel.purge(limit=limit, check=check, **kwargs)
            await ctx.send(f'Purge complete. Removed {len(msgs)} message(s).', delete_after=2.5)
        except discord.NotFound:
            pass  # ignore not found errors

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge(self, ctx, amount: int):
        """
        Purges messages the last <n> messages.

        This includes the purge command message. The bot will send a message
        upon completion, but will automatically be deleted.

        Note: The <n> that you specify will be the amount of messages checked,
              not deleted. This only applies to purge subcommands.
        """
        await self.base_purge(ctx, amount)

    @purge.command(name='by')
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge_by(self, ctx, target: discord.Member, amount: int = 5):
        """ Purges <n> messages from someone. """
        await self.base_purge(ctx, amount, lambda m: m.author == target)

    @purge.command(name='embeds')
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge_embeds(self, ctx, amount: int = 5):
        """ Purges <n> messages containing embeds. """
        await self.base_purge(ctx, amount, lambda m: len(m.embeds) != 0)

    @purge.command(name='attachments')
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge_attachments(self, ctx, amount: int = 5):
        """ Purges <n> messages containing attachments. """
        await self.base_purge(ctx, amount, lambda m: len(m.attachments) != 0)

    @purge.command(name='bot')
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge_bot(self, ctx, amount: int = 5):
        """ Purges <n> messages by bots. """
        await self.base_purge(ctx, amount, lambda m: m.author.bot)

    @commands.command()
    @commands.guild_only()
    async def clean(self, ctx):
        """ Removes recent messages posted by the bot. """
        try:
            await ctx.channel.purge(limit=50, check=lambda m: m.author == ctx.bot.user)
        except discord.NotFound:
            pass

    async def _check_who_action(self, ctx, action, target, action_past_tense):
        al_action = getattr(discord.AuditLogAction, action)
        try:
            target_id = int(target)
        except ValueError:
            target_id = None
        async for entry in ctx.guild.audit_logs(limit=None):
            if (entry.target.id == target_id or str(entry.target) == target) and entry.action == al_action:
                fmt = '{0} (`{0.id}`) has {3} {1} (`{1.id}`). Reason: {2}'
                return await ctx.send(fmt.format(entry.user, entry.target,
                                                 f'"{entry.reason}"' if entry.reason else
                                                 'No reason was provided.', action_past_tense))
        await ctx.send('I couldn\'t find the data from the audit logs. Sorry!')

    async def on_member_join(self, member):
        if not await self.bot.config_is_set(member.guild, 'welcome_message'):
            return

        welcome_message = (await self.bot.redis.get(f'{member.guild.id}:welcome_message')).decode()

        transformations = {
            '%{mention}': member.mention,
            '%{user}': str(member),
            '%{server}': member.guild.name,
            '%{id}': str(member.id)
        }

        for var, value in transformations.items():
            welcome_message = welcome_message.replace(var, value)

        await member.guild.default_channel.send(welcome_message)

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(view_audit_log=True)
    @checks.is_moderator()
    async def who_banned(self, ctx, *, someone: str):
        """
        Checks who banned a user.

        You may only specify the ID of the user (looks like: 305470090822811668), or
        the username and DiscordTag of a user (looks like: slice#0594).
        """
        await self._check_who_action(ctx, 'ban', someone, 'banned')

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(view_audit_log=True)
    @checks.is_moderator()
    async def who_kicked(self, ctx, *, someone: str):
        """
        Checks who kicked a user.

        You may only specify the ID of the user (looks like: 305470090822811668), or
        the username and DiscordTag of a user (looks like: slice#0594).
        """
        await self._check_who_action(ctx, 'kick', someone, 'kicked')

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(manage_roles=True)
    @checks.is_moderator()
    async def block(self, ctx, someone: discord.Member):
        """
        Blocks someone from reading your channel.

        This simply creates a channel permission overwrite which blocks
        an individual from having Read Messages in this channel.

        Any existing permission overwrites for the target is preserved.
        """
        if ctx.channel.is_default():
            await ctx.send('Members cannot be blocked from the default channel.')
            return
        existing_overwrite = ctx.channel.overwrites_for(someone)
        existing_overwrite.read_messages = False
        await ctx.channel.set_permissions(someone, overwrite=existing_overwrite)
        await ctx.ok()

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(manage_roles=True)
    @checks.is_moderator()
    async def unblock(self, ctx, someone: discord.Member):
        """
        Unblocks someone from reading your channel.

        Does the opposite of d?block.
        """
        overwrites = ctx.channel.overwrites_for(someone)
        can_read = overwrites.read_messages
        if can_read is None or can_read:
            # person isn't blocked
            await ctx.send('That person isn\'t (specifically) blocked.')
        elif not can_read:
            # person is blocked
            overwrites.read_messages = None
            if overwrites.is_empty():
                # overwrite is empty now, remove it
                logger.info('overwrite is empty')
                await ctx.channel.set_permissions(someone, overwrite=None)
            else:
                # overwrite still has stuff
                logger.info('overwrite still has things!')
                await ctx.channel.set_permissions(someone, overwrite=overwrites)
            await ctx.ok()

    @commands.command()
    @commands.guild_only()
    @checks.is_moderator()
    async def disable(self, ctx, command: str):
        """
        Disables a command in this server.

        In order to disable a group, simply pass in the group's name.
        For example: "d?disable feedback" will disable all feedback commands.
        """
        if self.bot.has_prefix(command):
            await ctx.send('You must leave off the prefix.')
            return
        await self.bot.disable_command(ctx.guild, command)
        await ctx.ok()

    @commands.command()
    @commands.guild_only()
    @checks.is_moderator()
    async def enable(self, ctx, command: str):
        """ Enables a command in this server. """
        if self.bot.has_prefix(command):
            await ctx.send('You must leave off the prefix.')
            return
        if not await self.bot.command_is_disabled(ctx.guild, command):
            await ctx.send('That command isn\'t disabled!')
            return
        await self.bot.enable_command(ctx.guild, command)
        await ctx.ok()

    @commands.command()
    @commands.guild_only()
    @checks.is_moderator()
    async def disabled(self, ctx):
        """ Shows disabled commands in this server. """
        keys = await self.bot.redis.keys(f'disabled:{ctx.guild.id}:*')
        disabled = ['d?' + k.decode().split(':')[2] for k in keys]

        if not disabled:
            await ctx.send('There are no disabled commands in this server.')
        else:
            await ctx.send(', '.join(disabled))

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @checks.bot_perms(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = None):
        """ Kicks someone. """
        try:
            await ctx.guild.kick(member, reason=reason)
        except discord.Forbidden:
            await ctx.send('I can\'t do that.')
        else:
            await ctx.ok()

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @checks.bot_perms(ban_members=True)
    async def ban(self, ctx, member: converters.RawMember, delete_days: int = 7, *, reason: str = None):
        """
        Bans someone.

        This command is special in that you may specify an ID to ban, instead of regularly specifying a
        member to ban. Banning users outside of the server is called "hackbanning", and is handy for banning
        users who are not present in the server.

        If you don't want to delete any messages, specify 0 for delete_days. delete_days has a
        maximum of 7. By default, 7 days worth of messages are deleted.
        """

        if delete_days > 7:
            raise commands.errors.BadArgument('`delete_days` has a maximum of 7.')

        try:
            await ctx.guild.ban(member, delete_message_days=delete_days, reason=reason)
        except discord.Forbidden:
            await ctx.send('I can\'t do that.')
        except discord.NotFound:
            await ctx.send('I couldn\'t find that user.')
        else:
            await ctx.ok()

    def _embed_field_for(self, member):
        return f'{member.mention} {member}'

    def _make_action_embed(self, executor, victim, **kwargs):
        embed = discord.Embed(**kwargs)
        embed.add_field(name='Who did it', value=self._embed_field_for(executor))
        embed.add_field(name='Who was it', value=self._embed_field_for(victim))
        embed.set_footer(text=utils.now())
        return embed

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @checks.bot_perms(manage_roles=True)
    async def vanity(self, ctx, *, name: str):
        """
        Creates a vanity role.

        A vanity role is defined as a role with no permissions.
        """
        perms = discord.Permissions(permissions=0)
        await ctx.guild.create_role(name=name, permissions=perms)
        await ctx.ok()

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @checks.bot_perms(manage_nicknames=True)
    async def attentionseek(self, ctx, replace_with: str = '💩'):
        """
        Changes attention-seeking nicknames.

        This will change the nickname of anybody whose name starts with "!"
        to a name you specify. By default, they are renamed to "💩".

        The renaming of attention-seekers is borrowed from the Discord API
        server.
        """
        attention_seekers = [m for m in ctx.guild.members if
                             m.display_name.startswith('!')]
        succeeded = len(attention_seekers)
        for seeker in attention_seekers:
            try:
                await seeker.edit(nick=replace_with)
            except:
                succeeded -= 1
        failed_count = len(attention_seekers) - succeeded
        await ctx.send(f'Renamed {succeeded} attention seeker(s).'
                       f' Failed to rename {failed_count}.')


def setup(bot):
    bot.add_cog(Mod(bot))
