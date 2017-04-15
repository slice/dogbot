import discord
from discord.ext import commands
from dog import Cog, utils, checks

class Modlog(Cog):
    def _make_modlog_embed(self, **kwargs):
        embed = discord.Embed(**kwargs)
        embed.set_footer(text=utils.now())
        return embed

    def _member_repr(self, member):
        return f'{member.mention} {member.name}#{member.discriminator}'

    def _make_profile_embed(self, member, **kwargs):
        _registered = (f'{utils.american_datetime(member.created_at)}'
                       f' ({utils.ago(member.created_at)} ago)')
        embed = self._make_modlog_embed(**kwargs)
        embed.add_field(name='Member', value=self._member_repr(member))
        embed.add_field(name='ID', value=member.id)
        embed.add_field(name='Registered on Discord', value=_registered)
        return embed

    async def on_message_delete(self, msg):
        # no it's not a typo
        delet_emote = '<:DeletThis:213623030197256203>'
        embed = self._make_modlog_embed(title=f'{delet_emote} Message deleted')

        # fields
        embed.add_field(name='Author', value=self._member_repr(msg.author))
        embed.add_field(name='Channel', value=f'{msg.channel.mention} {msg.channel.name}')
        embed.add_field(name='ID', value=msg.id)

        if msg.attachments:
            atts = [f'`{a["filename"]} ({a["width"]}×{a["height"]})`' for a
                    in msg.attachments]
            embed.add_field(name='Attachments', value=', '.join(atts))

        # set message content
        content = utils.truncate(msg.content, 1500)
        embed.description = content
        await self.bot.send_modlog(msg.guild, embed=embed)

    async def on_member_join(self, member):
        embed = self._make_profile_embed(member, title='\N{INBOX TRAY} Member joined')
        await self.bot.send_modlog(member.guild, embed=embed)

    async def on_member_remove(self, member):
        embed = self._make_profile_embed(member, title='\N{OUTBOX TRAY} Member removed')
        await self.bot.send_modlog(member.guild, embed=embed)

    async def on_member_ban(self, member):
        ban_emote = '<:Banhammer:243818902881042432>'
        embed = self._make_profile_embed(member, title=f'{ban_emote} Member banned')
        await self.bot.send_modlog(member.guild, embed=embed)

    async def on_member_unban(self, guild, user):
        embed = self._make_profile_embed(user, title='\N{SMILING FACE WITH HALO} Member unbanned')
        await self.bot.send_modlog(guild, embed=embed)

    async def on_channel_create(self, channel):
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
