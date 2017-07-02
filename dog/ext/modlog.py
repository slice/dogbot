"""
Contains the moderator log.
"""

import discord
import logging
from discord.ext import commands

from dog import Cog
from dog.core import checks, utils

logger = logging.getLogger(__name__)


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
        _registered = (f'{utils.standard_datetime(member.created_at)}'
                       f' ({utils.ago(member.created_at)})')
        embed = self._make_modlog_embed(**kwargs)
        embed.add_field(name='Member', value=self._member_repr(member))
        embed.add_field(name='ID', value=member.id)
        if not kwargs.get('omit_registered', False):
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
        if before.author.bot or before.content == after.content:
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

    def _make_member_changed_embed(self, attr: str, before, after, **kwargs) -> discord.Embed:
        b = getattr(before, attr, None)
        a = getattr(after, attr, None)
        verb = 'added' if not b and a else 'removed' if b and not a else 'changed'
        emoji = kwargs.get('emoji', '\N{CUSTOMS}')
        pretty_attr = kwargs.get('pretty_attr', attr.title())
        embed = self._make_profile_embed(after, omit_registered=True,
                                         title=f'{emoji} {pretty_attr} {verb}')
        embed.add_field(name=kwargs.get('before_title', 'From'),
                        value=b or f'<no {attr}>', inline=False)
        embed.add_field(name=kwargs.get('after_title', 'To'),
                        value=a or f'<no {attr}>', inline=False)
        return embed

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            embed = self._make_member_changed_embed('nick', before, after, pretty_attr='Nickname')
            await self.bot.send_modlog(before.guild, embed=embed)
        elif before.name != after.name:
            embed = self._make_member_changed_embed('name', before, after, pretty_attr='Username',
                                                    emoji='\N{NAME BADGE}')
            await self.bot.send_modlog(before.guild, embed=embed)

    async def on_message_delete(self, msg: discord.Message):
        if isinstance(msg.channel, discord.DMChannel):
            return

        if (not is_publicly_visible(msg.channel) or
                await self.bot.config_is_set(msg.guild, 'modlog_notrack_deletes')):
            return

        # no, i can't use and
        if msg.author.bot:
            if not await self.bot.config_is_set(msg.guild, 'modlog_filter_allow_bot'):
                return

        delete_symbol = '\N{DO NOT LITTER SYMBOL}'
        embed = self._make_message_embed(msg, title=f'{delete_symbol} Message deleted')

        if msg.attachments:
            def description(a):
                if a.width:
                    # is a picture
                    after = f'({a.width}×{a.height})'
                else:
                    # is a file
                    after = f'({a.size} bytes)'
                return f'`{a.filename} {after}`'

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

    @commands.command()
    async def is_public(self, ctx, channel: discord.TextChannel=None):
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
    async def modlog_setup(self, ctx: 'DogbotContext'):
        """ Sets up the modlog. """

        if discord.utils.get(ctx.guild.text_channels, name='mod-log'):
            await ctx.send('There is already a #mod-log in this server!')
            return

        await ctx.send('What roles do you want to grant `Read Messages` to'
                       ' in #mod-log? Example response: `rolename1,rolename2`'
                       '\nTo grant no roles access, respond with "none".')

        msg = await ctx.wait_for_response()

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
