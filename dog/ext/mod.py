"""
Contains commands that relate to server moderation and management.
"""
import logging
import re

import discord
import emoji
from discord.ext import commands

from dog import Cog
from dog.core import checks, converters
from dog.core.converters import DeleteDays
from dog.core.utils.formatting import describe

logger = logging.getLogger(__name__)

CUSTOM_EMOJI_REGEX = re.compile(r'<:([a-zA-Z_0-9-]+):(\d+)>')


class Mod(Cog):
    async def __global_check(self, ctx: commands.Context):
        # do not handle guild-specific command disables in dms
        if not isinstance(ctx.channel, discord.abc.GuildChannel):
            return True

        # role names that cannot use dog
        banned_names = (
            'Can\'t Use Dog', 'can\'t use dog', 'Dog Plonk', 'dog plonk', 'Banned from Dog', 'banned from dog'
        )

        if any(discord.utils.get(ctx.author.roles, name=name) for name in banned_names):
            return False

        return not await self.bot.command_is_disabled(ctx.guild, ctx.command.name)

    async def on_message(self, message: discord.Message):
        # do not handle invisibility in dms
        if isinstance(message.channel, discord.abc.PrivateChannel):
            return

        if await self.bot.config_is_set(message.guild, 'invisible_nag'):
            if message.author.status is discord.Status.offline:
                reply = 'Hey {0.mention}! You\'re invisible. Stop being invisible, please. Thanks.'
                await message.channel.send(reply.format(message.author))

    async def base_purge(self, ctx: commands.Context, limit: int, check=None, **kwargs):
        # check if it's too much
        if limit > 5000:
            await ctx.send('Too many messages to purge. 5,000 is the maximum.')
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

    @purge.command(name='by', aliases=['from'])
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge_by(self, ctx, target: discord.Member, amount: int = 5):
        """ Purges any message in the last <n> messages sent by someone. """
        await self.base_purge(ctx, amount, lambda m: m.author == target)

    @purge.command(name='embeds', aliases=['e'])
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge_embeds(self, ctx, amount: int = 5):
        """ Purges any message in the last <n> messages containing embeds. """
        await self.base_purge(ctx, amount, lambda m: len(m.embeds) != 0)

    @purge.command(name='attachments', aliases=['images', 'uploads', 'i'])
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge_attachments(self, ctx, amount: int = 5):
        """ Purges any message in the last <n> messages containing attachments. """
        await self.base_purge(ctx, amount, lambda m: len(m.attachments) != 0)

    @purge.command(name='bot')
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge_bot(self, ctx, amount: int = 5):
        """ Purges any message in the last <n> messages by bots. """
        await self.base_purge(ctx, amount, lambda m: m.author.bot)

    @purge.command(name='reactions')
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge_reactions(self, ctx: commands.Context, amount: int = 5):
        """ Purges reactions in the last <n> messages. """
        count = 0
        total_reactions_removed = 0

        async for message in ctx.history(limit=amount):
            # no reactions, skip
            if not message.reactions:
                continue

            # calculate total reaction count
            total_reactions_removed += sum(reaction.count for reaction in message.reactions)

            # remove all reactions
            await message.clear_reactions()
            count += 1

        await ctx.send(f'Purge complete. Removed {total_reactions_removed} reaction(s) from {count} message(s).',
                       delete_after=2.5)

    @purge.command(name='emoji', aliases=['emojis'])
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge_emoji(self, ctx, amount: int = 5, minimum_emoji: int = 1):
        """ Purges any message in the last <n> messages with emoji. """
        def message_check(msg):
            emoji_count = sum(1 for c in msg.content if c in emoji.UNICODE_EMOJI)
            return emoji_count >= minimum_emoji or CUSTOM_EMOJI_REGEX.search(msg.content) is not None
        await self.base_purge(ctx, amount, message_check)

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

        # scan the audit logs for the action they specified
        async for entry in ctx.guild.audit_logs(limit=None):
            # (id matches, or discordtag matches) && entry matches
            if (entry.target.id == target_id or str(entry.target) == target) and entry.action == al_action:
                # make readable string
                fmt = '{0} (`{0.id}`) has {3} {1} (`{1.id}`). Reason: {2}'
                return await ctx.send(fmt.format(entry.user, entry.target, f'"{entry.reason}"' if entry.reason else
                                                 'No reason was provided.', action_past_tense))

        # not found
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

        try:
            channel = discord.utils.get(member.guild.text_channels, name='welcome')
            await channel.send(welcome_message)
        except discord.Forbidden:
            logger.warning("Couldn't send welcome message for guild %d, no perms.", member.guild.id)

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(view_audit_log=True)
    @checks.is_moderator()
    async def who_banned(self, ctx, *, someone: str):
        """
        Checks who banned a user.

        You may only specify the ID of the user (looks like: 305470090822811668), or
        the username and DiscordTag of a user (looks like: slice#4274).
        """
        await self._check_who_action(ctx, 'ban', someone, 'banned')

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(manage_roles=True)
    @checks.is_moderator()
    async def lock(self, ctx):
        """
        Locks chat.

        This works by denying @everyone Send Messages.
        """
        try:
            await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        except discord.Forbidden:
            await ctx.send('I can\'t do that!')
        else:
            await ctx.ok()

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(manage_roles=True)
    @checks.is_moderator()
    async def unlock(self, ctx, explicit: bool = False):
        """
        Unlocks chat.

        This works by changing @everyone's Send Message permission
        back to neutral. To explicitly allow, pass "yes" as the first
        parameter.
        """
        value = True if explicit else None
        try:
            await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=value)
        except discord.Forbidden:
            await ctx.send('I can\'t do that!')
        else:
            await ctx.ok()

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
    async def block(self, ctx, *, someone: discord.Member):
        """
        Blocks someone from reading your channel.

        This simply creates a channel permission overwrite which blocks
        an individual from having Read Messages in this channel.

        Any existing permission overwrites for the target is preserved.
        """
        existing_overwrite = ctx.channel.overwrites_for(someone)
        existing_overwrite.read_messages = False
        await ctx.channel.set_permissions(someone, overwrite=existing_overwrite)
        await ctx.ok()

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(manage_roles=True)
    @checks.is_moderator()
    async def unblock(self, ctx, *, someone: discord.Member):
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
    async def mods(self, ctx):
        """
        Shows mods in this server.

        A mod is defined as a human in this server with the "Kick Members" permission, or is a Dogbot Moderator.
        """
        is_mod = lambda m: (m.guild_permissions.kick_members or checks.member_is_moderator(m)) and not m.bot
        mods = [m for m in ctx.guild.members if is_mod(m)]

        embed = discord.Embed(title='Moderators in ' + ctx.guild.name, color=discord.Color.blurple(),
                              description=f'There are {len(mods)} mod(s) total in {ctx.guild.name}.')

        for status in discord.Status:
            those_mods = [m for m in mods if m.status is status]
            if not those_mods:
                continue
            embed.add_field(name=str(status).title(), value='\n'.join(str(m) for m in those_mods))

        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @checks.bot_perms(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = None):
        """ Kicks someone. """
        try:
            await ctx.guild.kick(member, reason=f'(By {ctx.author}) {reason or "No reason provided."}')
        except discord.Forbidden:
            await ctx.send('I can\'t do that.')
        else:
            await ctx.send(f'\N{OK HAND SIGN} Kicked {describe(member)}.')

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @checks.bot_perms(ban_members=True)
    async def softban(self, ctx, member: discord.Member, delete_days: DeleteDays=2, *, reason: str=None):
        """
        Bans, then unbans someone.

        This is used to kick someone, also removing their messages. Behaves similarly to d?ban.
        """
        try:
            reason = f'(Softbanned by {ctx.author}) {reason or "No reason provided."}'
            await member.ban(delete_message_days=delete_days, reason=reason)
            await member.unban(reason=reason)
        except discord.Forbidden:
            await ctx.send("I can't do that.")
        else:
            await ctx.send(f'\N{OK HAND SIGN} **Soft**banned {describe(member)}.')

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @checks.bot_perms(ban_members=True)
    async def unban(self, ctx, member: converters.BannedUser, *, reason=''):
        """ Unbans someone. """
        await ctx.guild.unban(member, reason=f'(Unbanned by {ctx.author}) {reason or "No reason provided."}')
        await ctx.send(f'\N{OK HAND SIGN} Unbanned {describe(member)}.')

    @commands.command(aliases=['mban'])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @checks.bot_perms(ban_members=True)
    async def multiban(self, ctx, reason, delete_days: DeleteDays=2, *members: converters.RawMember):
        """
        Bans multiple users.

        Functions similarly to d?ban.
        """
        reason = reason or 'No reason provided.'
        log = []
        for member in members:
            try:
                await ctx.guild.ban(member, delete_message_days=delete_days,
                                    reason=f'(Multi-banned by {ctx.author}) {reason}')
                log.append(f'{ctx.green_tick} Banned {describe(member)}.')
            except discord.NotFound:
                # XXX: This code path might be unreachable, research further
                log.append("{ctx.red_tick} {member} wasn't found.")
            except (discord.Forbidden, discord.HTTPException):
                log.append(f'{ctx.red_tick} Failed to ban {describe(member)}.')
        await ctx.send('\n'.join(log))


    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @checks.bot_perms(ban_members=True)
    async def ban(self, ctx, member: converters.RawMember, delete_days: DeleteDays=2, *, reason=None):
        """
        Bans someone.

        This command is special in that you may specify an ID to ban, instead of regularly specifying a
        member to ban. Banning users outside of the server is called "hackbanning", and is handy for banning
        users who are not present in the server.

        If you don't want to delete any messages, specify 0 for delete_days. delete_days has a
        maximum of 7. By default, 2 days worth of messages are deleted.
        """
        try:
            reason = reason or 'No reason provided.'
            await ctx.guild.ban(member, delete_message_days=delete_days, reason=f'(Banned by {ctx.author}) {reason}')
        except discord.Forbidden:
            await ctx.send("I can't do that.")
        except discord.NotFound:
            await ctx.send("User not found.")
        else:
            banned = await ctx.bot.get_user_info(member.id) if isinstance(member, discord.Object) else member
            await ctx.send(f'\N{OK HAND SIGN} Banned {describe(banned)}.')

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @checks.bot_perms(manage_roles=True)
    async def vanity(self, ctx, name: str, assign_to: discord.Member = None, color: discord.Color = None):
        """
        Creates a vanity role.

        A vanity role is defined as a role with no permissions.
        """
        role = await ctx.guild.create_role(name=name, permissions=discord.Permissions.none(),
                                           color=color or discord.Color.default())
        if assign_to:
            try:
                await assign_to.add_roles(role)
            except (discord.Forbidden, discord.HTTPException):
                return await ctx.send(f"{ctx.red_tick} Couldn't give {role.name} to that person.")

        await ctx.send(f'{ctx.green_tick} Created vanity role {describe(role, quote=True)}.')

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @checks.bot_perms(manage_roles=True)
    async def empty_out(self, ctx, *, role: discord.Role):
        """
        Empties out a role's permissions.

        This effectively turn it into a vanity role.
        """
        if role > ctx.guild.me.top_role:
            return await ctx.send('My position on the role hierarchy is lower than that role, so I can\'t edit it.')

        try:
            await role.edit(permissions=discord.Permissions(permissions=0))
            await ctx.ok()
        except discord.Forbidden:
            await ctx.send('I can\'t do that.')

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
        attention_seekers = [m for m in ctx.guild.members if m.display_name.startswith('!')]
        succeeded = len(attention_seekers)
        for seeker in attention_seekers:
            try:
                await seeker.edit(nick=replace_with)
            except (discord.HTTPException, discord.Forbidden):
                succeeded -= 1
        failed_count = len(attention_seekers) - succeeded
        await ctx.send(f'Renamed {succeeded} attention seeker(s). Failed to rename {failed_count}.')


def setup(bot):
    bot.add_cog(Mod(bot))
