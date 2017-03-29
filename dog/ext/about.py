import discord
from subprocess import check_output
from discord.ext import commands
from dog import Cog, checks

owner_id = '97104885337575424'

class About(Cog):
    @commands.command()
    async def about(self):
        """ Shows information about the bot. """
        git_revision = check_output(['git', 'rev-parse', '--short', 'HEAD'])\
            .strip().decode('utf-8')
        maker = await self.bot.get_user_info(owner_id)
        embed = discord.Embed(
            title='Dogbot',
            description=f'A nice Discord bot by {maker.mention} ({maker.id}).'
            ' Available on GitHub [here](https://github.com/sliceofcode/dogbot)!')
        embed.add_field(name='Git revision', value=f'[{git_revision}](https://github.com/'
                        f'sliceofcode/dogbot/commit/{git_revision})')
        embed.set_footer(text=f'{maker.name}#{maker.discriminator}',
                         icon_url=maker.avatar_url)
        await self.bot.say(embed=embed)

    @commands.command()
    @checks.is_owner()
    async def stats(self):
        """ Shows participation info about the bot. """
        num_members = len(list(self.bot.get_all_members()))
        num_channels = len(list(self.bot.get_all_channels()))
        num_emojis = len(list(self.bot.get_all_emojis()))
        num_servers = len(self.bot.servers)

        embed = discord.Embed(title='Statistics')
        fields = {
            'Members': num_members,
            'Channels': num_channels,
            'Emojis': num_emojis,
            'Servers': num_servers,
        }
        for name, value in fields.items():
            embed.add_field(name=name, value=value)
        await self.bot.say(embed=embed)

def setup(bot):
    bot.add_cog(About(bot))
