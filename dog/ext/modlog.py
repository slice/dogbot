import discord
from discord.ext import commands
from dog import Cog, util

class Modlog(Cog):
    def _make_modlog_embed(self, **kwargs):
        embed = discord.Embed(**kwargs)
        embed.set_footer(text=util.now())
        return embed

    def _make_profile_embed(self, member, **kwargs):
        _registered = (f'{util.american_datetime(member.created_at)}'
                       f' ({util.ago(member.created_at)} ago)')
        embed = self._make_modlog_embed(**kwargs)
        embed.add_field(name='Member', value=f'{member.mention}'
                        f' {member.name}#{member.discriminator}')
        embed.add_field(name='ID', value=member.id)
        embed.add_field(name='Registered on Discord', value=_registered)
        return embed

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
    @commands.bot_has_permissions(manage_channels=True)
    async def setup_modlog(self, ctx):
        """ Sets up the modlog. """

        if 'mod-log' in [c.name for c in ctx.guild.channels]:
            await ctx.send('There is already a #mod-log in this server!')
            return

        await ctx.send('What roles do you want to grant `Read Messages` to'
                       ' in #mod-log? Example response: `rolename1,rolename2`'
                       '\nTo grant no roles access, respond with "none".')

        def check(m):
            return m.author == ctx.author
        msg = await self.bot.wait_for('message', check=check)

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
