import contextlib
import copy
import datetime
import io
import logging

import discord
from discord.ext import commands
from lifesaver.bot import Cog, Context, group
from ruamel.yaml import YAML

from dog.formatting import represent
from .keeper import Keeper


log = logging.getLogger(__name__)


def require_configuration():
    def predicate(ctx):
        if ctx.cog.gatekeeper_config(ctx.guild) == {}:
            raise commands.CheckFailure('Gatekeeper must be configured to use this command.')
        return True

    return commands.check(predicate)


class Gatekeeper(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.yaml = YAML()
        self.keepers = {}

    async def __local_check(self, ctx: Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage()

        if not ctx.author.guild_permissions.ban_members:
            raise commands.CheckFailure(
                'You can only manage Gatekeeper if you have the "Ban Members" '
                'permission.'
            )

        return True

    @property
    def dashboard_link(self):
        return self.bot.config.dashboard_link

    def gatekeeper_config(self, guild: discord.Guild):
        """Return Gatekeeper gatekeeper_config for a guild."""
        config = self.bot.guild_configs.get(guild) or {}
        return config.get('gatekeeper', {})

    def keeper(self, guild: discord.Guild) -> Keeper:
        """Return a long-lived Keeper instance for a guild.

        The Keeper instance is preserved in memory to contain state and other
        associated information.
        """
        alive_keeper = self.keepers.get(guild.id)

        if alive_keeper is not None:
            return alive_keeper

        # create a new keeper instance for the guild
        config = self.gatekeeper_config(guild)
        log.debug('creating a new keeper for guild %d (config=%r)', guild.id, config)
        keeper = Keeper(guild, config, bot=self.bot)
        self.keepers[guild.id] = keeper
        return keeper

    @Cog.listener()
    async def on_guild_config_edit(self, guild: discord.Guild, config):
        if guild.id not in self.keepers:
            log.debug('received config edit for keeperless guild %d', guild.id)
            return

        log.debug('updating keeper config for guild %d', guild.id)
        self.keepers[guild.id].update_config(config.get('gatekeeper', {}))

    @contextlib.asynccontextmanager
    async def edit_config(self, guild: discord.Guild):
        config = self.bot.guild_configs.get(guild) or {}
        copied_gatekeeper_config = copy.deepcopy(config['gatekeeper'])
        yield copied_gatekeeper_config

        with io.StringIO() as buffer:
            self.yaml.indent(mapping=4, sequence=6, offset=4)
            self.yaml.dump({
                **config,
                'gatekeeper': copied_gatekeeper_config,
            }, buffer)
            await self.bot.guild_configs.write(guild, buffer.getvalue())

    @Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.bot.wait_until_ready()

        config = self.gatekeeper_config(member.guild)

        if not config.get('enabled', False):
            return

        # fetch the keeper instance for this guild, which manages gatekeeping,
        # check processing, and all of that good stuff.
        keeper = self.keeper(member.guild)

        overridden = config.get('allowed_users', [])
        is_whitelisted = str(member) in overridden or member.id in overridden

        if not is_whitelisted:
            # this function will do the reporting for us if the user fails any
            # checks.
            is_allowed = await keeper.check(member)

            if not is_allowed:
                return

        if config.get('quiet', False):
            return

        embed = discord.Embed(
            color=discord.Color.green(),
            title=f'{represent(member)} has joined',
            description='This user has passed all Gatekeeper checks.'
        )

        if is_whitelisted:
            embed.description = 'This user has been specifically allowed into this server.'

        embed.set_thumbnail(url=member.avatar_url)
        embed.timestamp = datetime.datetime.utcnow()

        await keeper.report(embed=embed)

    @group(aliases=['gk'], hollow=True)
    async def gatekeeper(self, ctx: Context):
        """
        Manages Gatekeeper.

        Gatekeeper is an advanced mechanism of Dogbot that allows you to screen member joins in realtime,
        and automatically kick those who don't fit a certain criteria. Only users who can ban can use it.
        This is very useful when your server is undergoing raids, unwanted attention, unwanted members, etc.
        """

    @gatekeeper.command(name='lockdown', aliases=['ld'])
    @require_configuration()
    async def command_lockdown(self, ctx: Context, *, enabled: bool = True):
        """Enables block_all.

        You can also provide "on" or "off" to the command to manually enable
        or disable the check as desired.
        """
        async with self.edit_config(ctx.guild) as config:
            checks = config.get('checks', {})
            checks['block_all'] = {'enabled': enabled}
            config['checks'] = checks

        status = 'enabled' if enabled else 'disabled'
        await ctx.send(f'{ctx.tick()} `block_all` is now {status}.')

    @gatekeeper.command(name='enable', aliases=['on'])
    @require_configuration()
    async def command_enable(self, ctx: Context):
        """Enables Gatekeeper."""
        async with self.edit_config(ctx.guild) as config:
            config['enabled'] = True

        await ctx.send(f'{ctx.tick()} Enabled Gatekeeper.')

    @gatekeeper.command(name='disable', aliases=['off'])
    @require_configuration()
    async def command_disable(self, ctx: Context):
        """Disables Gatekeeper."""
        async with self.edit_config(ctx.guild) as config:
            config['enabled'] = False

        await ctx.send(f'{ctx.tick()} Disabled Gatekeeper.')

    @gatekeeper.command(name='toggle', aliases=['flip'])
    @require_configuration()
    async def command_toggle(self, ctx: Context):
        """Toggles Gatekeeper."""
        async with self.edit_config(ctx.guild) as config:
            config['enabled'] = not config['enabled']

        state = 'enabled' if config['enabled'] else 'disabled'

        await ctx.send(f'{ctx.tick()} Gatekeeper is now {state}.')

    @gatekeeper.command(name='status')
    @require_configuration()
    async def command_status(self, ctx: Context):
        """Views the current status of Gatekeeper."""
        enabled = self.gatekeeper_config(ctx.guild).get('enabled', False)

        if enabled:
            description = 'Incoming members must pass Gatekeeper checks to join.'
        else:
            description = 'Anyone can join.'

        link = f'{self.dashboard_link}/guilds/{ctx.guild.id}'
        description += f'\n\nUse [the web dashboard]({link}) to configure gatekeeper.'

        if enabled:
            color = discord.Color.green()
        else:
            color = discord.Color.red()

        embed = discord.Embed(
            color=color,
            title=f'Gatekeeper is {"on" if enabled else "off"}.',
            description=description,
        )

        await ctx.send(embed=embed)
