import asyncio
import discord
from discord.ext import commands
from dog import Cog, checks
from dog.humantime import HumanTime


class Mod(Cog):
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member):
        """ Kicks someone. """
        await ctx.guild.kick(member)
        await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def ban(self, ctx, member: discord.Member, days: int=0):
        """ Bans someone from the server. """
        await ctx.guild.ban(member, days)
        await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
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

        try:
            await member.remove_roles(mute_role)
            await ctx.send(f'\N{SPEAKER} Unmuted {member.name}#{member.discriminator}'
                           f' (`{member.id}`)')
        except discord.Forbidden:
            await ctx.send('\N{CROSS MARK} I can\'t do that!')
        except:
            await ctx.send('\N{CROSS MARK} I failed to do that.')

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(manage_channels=True)
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

            # use a check to only accept responses from the message author
            def predicate(m):
                return m.author.id == ctx.message.author.id
            msg = await self.bot.wait_for('message', check=predicate)

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
                               f' am excluding:\n\n{formatted_exclusions}')
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
                    await channel.set_permissions(mute_role, overwrite=None)
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
    @commands.bot_has_permissions(manage_roles=True)
    @checks.is_moderator()
    async def mute(self, ctx, member: discord.Member, time: HumanTime):
        """
        Mutes someone for a certain amount of time.

        The "Muted" role must exist on the server in order for this to work.
        The bot will not setup "Muted" channel overrides for you, you must
        do it yourself.

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
        except:
            await msg.edit(content='\N{CROSS MARK} I failed to do that.')

        async def unmute_task():
            await asyncio.sleep(time.seconds)
            await member.remove_roles(mute_role)
            if await self.bot.config_is_set(ctx.guild, 'unmute_announce'):
                await ctx.send(f'\N{SPEAKER} {member.name}#{member.discriminator}'
                               f' (`{member.id}`) has been unmuted.')

        self.bot.loop.create_task(unmute_task())

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_nicknames=True)
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
