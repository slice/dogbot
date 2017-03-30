import inspect
import datetime
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
    async def source(self, command: str):
        """ Shows the source code of a command. """
        cmd = self.bot.get_command(command)

        if cmd is None:
            await self.bot.say('No such command!')
            return

        sourcefile = inspect.getsourcefile(cmd.callback)
        sourcelines = inspect.getsourcelines(cmd.callback)
        short_path = '/'.join(sourcefile.split('/')[-2:])

        root = 'https://github.com/sliceofcode/dogbot/tree/master/dog'
        start = sourcelines[1]
        await self.bot.say(f'{root}/{short_path}#L{start}')

    @commands.command()
    @checks.is_owner()
    async def stats(self):
        """ Shows participation info about the bot. """
        num_members = len(list(self.bot.get_all_members()))
        num_channels = len(list(self.bot.get_all_channels()))
        num_servers = len(self.bot.servers)
        uptime = str(datetime.datetime.utcnow() - self.bot.boot_time)[:-7]

        embed = discord.Embed(title='Statistics',
                              description='Statistics and participation information.')
        fields = {
            'Members': num_members,
            'Channels': num_channels,
            'Servers': num_servers,
            'Uptime': uptime,
        }
        for name, value in fields.items():
            embed.add_field(name=name, value=value)
        await self.bot.say(embed=embed)

def setup(bot):
    bot.add_cog(About(bot))
