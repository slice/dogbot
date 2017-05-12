"""
Contains the moderator log.
"""

import discord
from discord.ext import commands

from dog import Cog
from dog.core import checks, utils


def is_publicly_visible(channel: discord.TextChannel) -> bool:
    """ Returns whether a channel is publicly visible with the default role. """
    everyone_overwrite = discord.utils.find(lambda t: t[0].name == '@everyone',
                                            channel.overwrites)
    return everyone_overwrite is None or everyone_overwrite[1].read_messages is not False


class Modlog(Cog):
    def _make_modlog_embed(self, **kwargs):
        embed = discord.Embed(**kwargs)
        embed.set_footer(text=utils.now())
        return embed

    def _member_repr(self, member: discord.Member) -> str:
        return f'{member.mention} {member.name}#{member.discriminator}'

    def _make_profile_embed(self, member: discord.Member, **kwargs) -> discord.Embed:
        _registered = (f'{utils.american_datetime(member.created_at)}'
                       f' ({utils.ago(member.created_at)})')
        embed = self._make_modlog_embed(**kwargs)
        embed.add_field(name='Member', value=self._member_repr(member))
        embed.add_field(name='ID', value=member.id)
        embed.add_field(name='Registered on Discord', value=_registered)
        return embed

    def _make_message_embed(self, msg: discord.Message, **kwargs) -> discord.Embed:
        embed = self._make_modlog_embed(**kwargs)
        if kwargs.get('add_content', False):
            embed.description = msg.content
        embed.add_field(name='Author', value=self._member_repr(msg.author))
        embed.add_field(name='Channel', value=f'{msg.channel.mention} {msg.channel.name}')
        embed.add_field(name='ID', value=msg.id)
        return embed

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot:
            return

        if before.content == after.content:
            return

        if (not is_publicly_visible(before.channel) or
                await self.bot.config_is_set(before.guild, 'modlog_notrack_edits')):
            return

        embed = self._make_message_embed(before, title=f'\N{MEMO} Message edited')
        embed.add_field(name='Before', value=utils.truncate(before.content or '<empty>', 1024),
                        inline=False)
        embed.add_field(name='After', value=utils.truncate(after.content or '<empty>', 1024),
                        inline=False)
        await self.bot.send_modlog(before.guild, embed=embed)

    async def on_message_delete(self, msg: discord.Message):
        if (not is_publicly_visible(msg.channel) or
                await self.bot.config_is_set(msg.guild, 'modlog_notrack_deletes')):
            return

        # no, i can't use and
        if msg.author.bot:
            if not await self.bot.config_is_set(msg.guild, 'modlog_filter_allow_bot'):
                return

        # no it's not a typo
        delet_emote = '<:DeletThis:213623030197256203>'
        embed = self._make_message_embed(msg, title=f'{delet_emote} Message deleted')

        if msg.attachments:
            def description(a):
                if "width" in a:
                    # is a picture
                    after = f'({a["width"]}×{a["height"]})'
                else:
                    # is a file
                    after = f'({a["size"]} bytes)'
                return f'`{a["filename"]} {after}`'

            atts = [description(a) for a in msg.attachments]
            embed.add_field(name='Attachments', value=', '.join(atts))

        # set message content
        embed.description = msg.content  # description limit = 2048, message content limit = 2000
        await self.bot.send_modlog(msg.guild, embed=embed)

    async def on_member_join(self, member: discord.Member):
        embed = self._make_profile_embed(member, title='\N{INBOX TRAY} Member joined')
        await self.bot.send_modlog(member.guild, embed=embed)

    async def on_member_remove(self, member: discord.Member):
        embed = self._make_profile_embed(member, title='\N{OUTBOX TRAY} Member removed')
        await self.bot.send_modlog(member.guild, embed=embed)

    async def on_member_ban(self, member: discord.Member):
        ban_emote = '<:Banhammer:243818902881042432>'
        embed = self._make_profile_embed(member, title=f'{ban_emote} Member banned')
        await self.bot.send_modlog(member.guild, embed=embed)

    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = self._make_profile_embed(user, title='\N{SMILING FACE WITH HALO} Member unbanned')
        await self.bot.send_modlog(guild, embed=embed)

    async def on_channel_create(self, channel):
        if isinstance(channel, discord.DMChannel):
            return

        embed = self._make_modlog_embed(title='\N{SPARKLES} New channel')
        embed.add_field(name='Channel', value=f'{channel.mention} {channel.name}')
        embed.add_field(name='ID', value=channel.id)
        await self.bot.send_modlog(channel.guild, embed=embed)

    async def on_channel_delete(self, channel):
        embed = self._make_modlog_embed(title='\N{HAMMER} Channel deleted')
        embed.add_field(name='Channel', value=f'{channel.name}')
        embed.add_field(name='ID', value=channel.id)
        await self.bot.send_modlog(channel.guild, embed=embed)

    @commands.command()
    async def is_public(self, ctx, channel: discord.TextChannel = None):
        """
        Checks if a channel is public.

        This command is in the Modlog cog because the modlog does not process message edit and
        delete events for private channels.
        """
        channel = channel if channel else ctx.channel
        public = f'{channel.mention} {{}} public to @\u200beveryone.'
        await ctx.send(public.format('is' if is_publicly_visible(channel) else '**is not**'))

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    @checks.bot_perms(manage_channels=True)
    async def modlog_setup(self, ctx):
        """ Sets up the modlog. """

        if 'mod-log' in [c.name for c in ctx.guild.channels]:
            await ctx.send('There is already a #mod-log in this server!')
            return

        await ctx.send('What roles do you want to grant `Read Messages` to'
                       ' in #mod-log? Example response: `rolename1,rolename2`'
                       '\nTo grant no roles access, respond with "none".')

        msg = await self.bot.wait_for_response(ctx)

        if msg.content == 'none':
            await ctx.send('Granting no roles access.')
            roles = []
        else:
            roles = [discord.utils.get(ctx.guild.roles, name=n) for n in msg.content.split(',')]

        if None in roles:
            await ctx.send('You provided an invalid role name somewhere!')
            return

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(send_messages=True, read_messages=True),
        }

        role_overwrites = {role: discord.PermissionOverwrite(read_messages=True) for role in roles}
        overwrites.update(role_overwrites)

        ch = await ctx.guild.create_text_channel('mod-log', overwrites=overwrites)

        await ctx.send(f'Created {ch.mention}!')


def setup(bot):
    bot.add_cog(Modlog(bot))
