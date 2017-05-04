"""
Contains commands that relate to server moderation and management.
"""

import asyncio
import logging

import discord
from discord.ext import commands

from dog import Cog
from dog.core import checks, utils
from dog.humantime import HumanTime

logger = logging.getLogger(__name__)


class Mod(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mute_tasks = {}

    async def __global_check(self, ctx: commands.Context):
        # do not handle guild-specific command disables in
        # dms
        if not isinstance(ctx.channel, discord.abc.GuildChannel):
            return True

        banned_names = [
            'Can\'t Use Dog', 'can\'t use dog', 'Dog Plonk', 'dog plonk',
            'Banned from Dog', 'banned from dog'
        ]

        for banned_name in banned_names:
            if discord.utils.get(ctx.author.roles, name=banned_name):
                return False

        return not await self.bot.command_is_disabled(ctx.guild, ctx.command.name)

    async def on_message(self, message: discord.Message):
        # do not handle invisibility in dms
        if isinstance(message.channel, discord.abc.PrivateChannel):
            return

        if await self.bot.config_is_set(message.guild, 'invisible_announce'):
            if message.author.status is discord.Status.offline:
                reply = ('Hey {0.mention}! You\'re invisible. Stop being '
                         'invisible, please. Thanks.')
                await message.channel.send(reply.format(message.author))

    async def base_purge(self, ctx: commands.Context, limit: int, check=None, **kwargs):
        # check if it's too much
        if limit > 1000:
            await ctx.send('Too many messages to purge. 1,000 is the maximum.')
            return

        # purge the actual command message too
        limit += 1

        msgs = await ctx.channel.purge(limit=limit, check=check, **kwargs)
        await ctx.send(f'Purge complete. Removed {len(msgs)} message(s).',
                       delete_after=2.5)

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
    async def purge_by(self, ctx, target: discord.Member, amount: int = 5):
        """ Purges <n> messages from someone. """
        await self.base_purge(ctx, amount, lambda m: m.author.id == target.id)

    @purge.command(name='dog')
    async def purge_dog(self, ctx, amount: int = 5):
        """ Purges <n> messages by me (dogbot). """
        await self.base_purge(ctx, amount, lambda m: m.author.id == self.bot.user.id)

    @purge.command(name='embeds')
    async def purge_embeds(self, ctx, amount: int = 5):
        """ Purges <n> messages containing embeds. """
        await self.base_purge(ctx, amount, lambda m: len(m.embeds) != 0)

    @purge.command(name='attachments')
    async def purge_attachments(self, ctx, amount: int = 5):
        """ Purges <n> messages containing attachments. """
        await self.base_purge(ctx, amount, lambda m: len(m.attachments) != 0)

    @purge.command(name='bot')
    async def purge_bot(self, ctx, amount: int = 5):
        """ Purges <n> messages by bots. """
        await self.base_purge(ctx, amount, lambda m: m.author.bot)

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

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(view_audit_logs=True)
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
    @checks.bot_perms(view_audit_logs=True)
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
        await self.bot.ok(ctx)

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
            await self.bot.ok(ctx)

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
        await self.bot.ok(ctx)

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
        await self.bot.ok(ctx)

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
    async def kick(self, ctx, member: discord.Member):
        """ Kicks someone. """
        try:
            await ctx.guild.kick(member)
        except discord.Forbidden:
            await ctx.send('I can\'t do that.')
        else:
            await self.bot.ok(ctx)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @checks.bot_perms(ban_members=True)
    async def ban(self, ctx, member: discord.Member, days: int=0):
        """ Bans someone. """
        try:
            await ctx.guild.ban(member, delete_message_days=days)
        except discord.Forbidden:
            await ctx.send('I can\'t do that.')
        else:
            await self.bot.ok(ctx)

    def _embed_field_for(self, member):
        return f'{member.mention} {member.name}#{member.discriminator}'

    def _make_action_embed(self, executor, victim, **kwargs):
        embed = discord.Embed(**kwargs)
        embed.add_field(name='Who did it', value=self._embed_field_for(executor))
        embed.add_field(name='Who was it', value=self._embed_field_for(victim))
        embed.set_footer(text=utils.now())
        return embed

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(manage_roles=True)
    @checks.is_moderator()
    async def unmute(self, ctx, member: discord.Member):
        """ Instantly unmutes someone. """
        mute_role = discord.utils.get(ctx.guild.roles, name='Muted')

        if not mute_role:
            await ctx.send('\N{CROSS MARK} I can\'t find the "Muted" role.')
            return

        if mute_role not in member.roles:
            await ctx.send(f'\N{SPEAKER} That person isn\'t muted.')
            return

        if member in self.mute_tasks:
            # cancel the mute task, so they don't get unmuted when the
            # task awakens
            self.mute_tasks[member].cancel()

        try:
            await member.remove_roles(mute_role)
            await ctx.send(f'\N{SPEAKER} Unmuted {member.name}#{member.discriminator}'
                           f' (`{member.id}`).')
        except discord.Forbidden:
            await ctx.send('\N{CROSS MARK} I can\'t do that!')
            return
        except:
            await ctx.send('\N{CROSS MARK} I failed to do that.')
            return

        embed = self._make_action_embed(ctx.author, member,
                                        title='\N{SPEAKER} Member force-unmuted')
        await self.bot.send_modlog(ctx.guild, embed=embed)

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(manage_channels=True)
    @checks.is_moderator()
    async def mute_setup(self, ctx):
        """
        Sets up "Muted" permission overrides for all channels.

        If the "Muted" role was not found, it will be created.
        By default, the permission overrides will deny the "Send Messages"
        permission for the people with the "Muted" role. If you want to deny
        the "Read Message" permissions for "Muted" people too, you must set
        the "mutesetup_disallow_read" key. You can do this with
            d?config set mutesetup_disallow_read
        Then, run d?muted_setup. If you already did, you must re-run it.

        Note: If you set that key, you will be prompted to provide a list of
        channels that will be readable (but not writable) of "Muted" status.
        """
        mute_role = discord.utils.get(ctx.guild.roles, name='Muted')

        if not mute_role:
            msg = await ctx.send('There is no "Muted" role, I\'ll set it up '
                                 'for you.')
            try:
                mute_role = await ctx.guild.create_role(name='Muted')
            except discord.Forbidden:
                await msg.edit(content='I couldn\'t find the "Muted" role,'
                                       'and I couldn\'t create it either!')
                return

        mute_options = {
            'send_messages': False
        }
        exclusion_list = []

        # beacuse we are disallowing read perms, there may be some channels
        # that people will still need to look at, even when muted.
        # so, prompt the moderator for a list of channels that will still
        # be readable (but not writable) regardless of mute status
        if await self.bot.config_is_set(ctx.guild, 'mutesetup_disallow_read'):
            mute_options['read_messages'] = False
            await ctx.send("""Okay! Please provide a comma separated list of channel
names for me to **exclude from being hidden from users
while they are muted**. For example, you probably don't
want muted users to not be able to see a channel like
#announcements!

If you don't want to exclude any channels, just type "none" and send it.

Example response: "announcements,corkboard,etc"
**Do not mention the channel, or put spaces anywhere.**""")

            msg = await self.bot.wait_for_response(ctx)

            if msg.content != "none":
                # create an exclusion list from the message
                exclusion_list = [discord.utils.get(ctx.guild.channels, name=c)
                                  for c in msg.content.split(',')]

                # if discord.utils.get returned None at some point, then that
                # means that one of the channels could not be found.
                if None in exclusion_list:
                    await ctx.send('Sorry! I didn\'t find one of the channels '
                                   'you listed, or your exclusion list was '
                                   'invalid. Please try the command again.')
                    return

                # format the exclusion list to look nice
                formatted_exclusions = '\n'.join([f'• {c.mention}' for c in
                                                  exclusion_list])

                # say the channels that will be excluded
                await ctx.send('For reference, here is the list of channels I'
                               ' am excluding from being hidden while muted:'
                               f'\n\n{formatted_exclusions}')
            else:
                await ctx.send('Alright, I won\'t exclude any channels.')

        failed = []
        succeeded = 0

        prg = await ctx.send('Doing it...')

        for channel in ctx.guild.channels:
            overwrite = discord.PermissionOverwrite(**mute_options)
            try:
                # if the channel is in the exclusion list, just delete
                # the overwrite
                if channel in exclusion_list:
                    await channel.set_permissions(mute_role, send_messages=False)
                else:
                    await channel.set_permissions(mute_role,
                                                  overwrite=overwrite)
            except discord.Forbidden:
                failed.append(channel.mention)
            else:
                if channel not in exclusion_list:
                    succeeded += 1

        if failed:
            await prg.edit(content=f'All done! I failed to edit **{len(failed)}**'
                                   f' channel(s): {", ".join(failed)}')
        else:
            await prg.edit(content='All done! Everything went OK. I modified '
                           f'{succeeded} channel(s). Note: This server\'s'
                           f' default channel, {ctx.guild.default_channel.mention},'
                           f' can always be read, even if someone is muted.'
                           ' (This is a Discord thing.)')

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
        await self.bot.ok(ctx)

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(manage_roles=True)
    @checks.is_moderator()
    async def mute(self, ctx, member: discord.Member, time: HumanTime):
        """
        Mutes someone for a certain amount of time.

        The "Muted" role must exist on the server in order for this to work.
        The bot can setup the "Muted" role and channel overrides for you
        with the d?mute_setup command.

        d?mute <someone> 5m
            Mutes someone for 5 minutes.
        d?mute <someone> 2h5m
            Mutes someone for 2 hours and 5 minutes.
        d?mute <someone> 5s
            Mutes someone for 5 seconds.
        """
        mute_role = discord.utils.get(ctx.guild.roles, name='Muted')

        if not mute_role:
            await ctx.send('\N{CROSS MARK} I can\'t find the "Muted" role.')
            return

        mute = '\N{SPEAKER WITH CANCELLATION STROKE}'
        sec = utils.commas(time.seconds)
        msg = await ctx.send(f'{mute} Muting {member.name}#{member.discriminator}'
                             f' (`{member.id}`) for {time.raw} ({sec} seconds).')

        try:
            await member.add_roles(mute_role)
        except discord.Forbidden:
            await msg.edit(content='\N{CROSS MARK} I can\'t do that!'
                           ' I might be too low on the role hierarchy,'
                           ' or I need permissions.'
                           ' Ensure that the my bot role is placed above'
                           ' the "Muted" role.')
            return
        except:
            await msg.edit(content='\N{CROSS MARK} I failed to do that.')
            return

        async def unmute_task():
            await asyncio.sleep(time.seconds)
            await member.remove_roles(mute_role)
            if await self.bot.config_is_set(ctx.guild, 'unmute_announce'):
                await ctx.send(f'\N{SPEAKER} {member.name}#{member.discriminator}'
                               f' (`{member.id}`) has been unmuted.')

        task = self.bot.loop.create_task(unmute_task())
        self.mute_tasks[member] = task

        embed = self._make_action_embed(ctx.author, member, title=f'{mute} Member muted')
        embed.add_field(name='Duration', value=f'{time.raw} ({time.seconds}s)')
        await self.bot.send_modlog(ctx.guild, embed=embed)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @checks.bot_perms(manage_nicknames=True)
    async def attentionseek(self, ctx, replace_with: str='💩'):
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
