import logging
import asyncio
import discord
from discord.ext import commands
from dog import Cog, checks, util
from dog.humantime import HumanTime

logger = logging.getLogger(__name__)

class Mod(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mute_tasks = {}

    async def __global_check(self, ctx):
        # do not handle guild-specific command disables in
        # dms
        if not isinstance(ctx.channel, discord.abc.GuildChannel):
            return True

        return not await self.bot.command_is_disabled(ctx.guild, ctx.command.name)

    async def on_message(self, message):
        # do not handle invisibility in dms
        if isinstance(message.channel, discord.abc.PrivateChannel):
            return

        if await self.bot.config_is_set(message.guild, 'invisible_announce'):
            if message.author.status is discord.Status.offline:
                reply = ('Hey {0.mention}! You\'re invisible. Stop being '
                         'invisible, please. Thanks.')
                await message.channel.send(reply.format(message.author))

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(manage_messages=True, read_message_history=True)
    @checks.is_moderator()
    async def purge(self, ctx, amount: int):
        """
        Purges messages the last <n> messages.
        """

        # increase one because the command message they sent needs
        # to be purged, too.
        amount = amount + 1
        if amount > 501:
            await ctx.send('That number is too big! 500 is the max.')
            return

        # purge the channel
        messages = await ctx.channel.purge(limit=amount)

        # complete!
        await ctx.send(f'Purge complete. Removed {len(messages)}/{amount}'
                       ' messages.', delete_after=2.5)

    @commands.command()
    @commands.guild_only()
    @checks.bot_perms(manage_roles=True)
    @checks.is_moderator()
    async def block(self, ctx, someone: discord.Member):
        """
        Blocks someone from reading your channel.

        This simply creates a channel permission overwrite which blocks
        an individual from having Read Messages in this channel.
        """
        if ctx.channel == ctx.guild.default_channel:
            await ctx.send('Members cannot be blocked from the default channel.')
            return
        await ctx.channel.set_permissions(someone, read_messages=False)
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
        """ Shows you disabled commands in this server. """
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
        """ Bans someone from the server. """
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
        embed.set_footer(text=util.now())
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
    async def vanity(self, ctx, name: str):
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
        msg = await ctx.send(f'{mute} Muting {member.name}#{member.discriminator}'
                             f' (`{member.id}`) for {time.seconds} second(s).')

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
