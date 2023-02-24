import asyncio
import contextlib
import copy
import datetime
import io
import logging

import discord
import lifesaver
from discord.ext import commands
from lifesaver.utils import pluralize
from ruamel.yaml import YAML

from dog.formatting import represent

from .converters import UserReference
from .keeper import Keeper

log = logging.getLogger(__name__)


def require_configuration():
    def predicate(ctx):
        if not ctx.cog.gatekeeper_config(ctx.guild):
            raise commands.CheckFailure(
                "Gatekeeper must be configured to use this command."
            )
        return True

    return commands.check(predicate)


class Gatekeeper(lifesaver.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.yaml = YAML()
        self.keepers = {}

    async def cog_check(self, ctx: lifesaver.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage()

        if not ctx.bot.guild_configs.can_edit(ctx.author, ctx.guild):
            raise commands.CheckFailure("You aren't allowed to manage Gatekeeper.")

        return True

    @property
    def dashboard_link(self):
        return self.bot.config.dashboard_link

    def gatekeeper_config(self, guild: discord.Guild):
        """Return Gatekeeper gatekeeper_config for a guild."""
        config = self.bot.guild_configs.get(guild, {})
        return config.get("gatekeeper", {})

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
        log.debug("creating a new keeper for guild %d (config=%r)", guild.id, config)
        keeper = Keeper(guild, config, bot=self.bot)
        self.keepers[guild.id] = keeper
        return keeper

    @lifesaver.Cog.listener()
    async def on_guild_config_edit(self, guild: discord.Guild, config):
        if guild.id not in self.keepers:
            log.debug("received config edit for keeperless guild %d", guild.id)
            return

        log.debug("updating keeper config for guild %d", guild.id)
        self.keepers[guild.id].update_config(config.get("gatekeeper", {}))

    @contextlib.asynccontextmanager
    async def edit_config(self, guild: discord.Guild):
        config = self.bot.guild_configs.get(guild, {})
        copied_gatekeeper_config = copy.deepcopy(config["gatekeeper"])
        yield copied_gatekeeper_config

        with io.StringIO() as buffer:
            self.yaml.indent(mapping=4, sequence=6, offset=4)
            self.yaml.dump(
                {
                    **config,
                    "gatekeeper": copied_gatekeeper_config,
                },
                buffer,
            )
            await self.bot.guild_configs.write(guild, buffer.getvalue())

    def is_being_allowed(self, guild: discord.Guild, user) -> bool:
        """Return whether a user is being specifically allowed."""
        return user in self.gatekeeper_config(guild).get("allowed_users", [])

    async def allow_user(self, guild: discord.Guild, user):
        """Allow a user to bypass checks in a guild."""
        async with self.edit_config(guild) as config:
            allowed_users = config.get("allowed_users", [])
            # have to do manual replacement in case we get []
            config["allowed_users"] = allowed_users + [user]

    async def disallow_user(self, guild: discord.Guild, user):
        """Disallow a user to bypass checks in a guild."""
        async with self.edit_config(guild) as config:
            allowed_users = config.get("allowed_users", [])
            allowed_users.remove(user)

    @lifesaver.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.bot.wait_until_ready()

        config = self.gatekeeper_config(member.guild)

        if not config.get("enabled", False):
            return

        # fetch the keeper instance for this guild, which manages gatekeeping,
        # check processing, and all of that good stuff.
        keeper = self.keeper(member.guild)

        overridden = config.get("allowed_users", [])
        is_whitelisted = str(member) in overridden or member.id in overridden

        if not is_whitelisted:
            # this function will do the reporting for us if the user fails any
            # checks.
            is_allowed = await keeper.check(member)

            if not is_allowed:
                return

        if config.get("quiet", False):
            return

        embed = discord.Embed(
            color=discord.Color.green(),
            title=f"{represent(member)} has joined",
            description="This user has passed all Gatekeeper checks.",
        )

        if is_whitelisted:
            embed.description = (
                "This user has been specifically allowed into this server."
            )

        embed.set_thumbnail(url=str(member.avatar))
        embed.timestamp = discord.utils.utcnow()

        await keeper.report(embed=embed)

    @lifesaver.group(aliases=["gk"], hollow=True)
    async def gatekeeper(self, ctx: lifesaver.Context):
        """
        Manages Gatekeeper.

        Gatekeeper is an advanced mechanism of Dogbot that allows you to screen member joins in realtime,
        and automatically kick those who don't fit a certain criteria. Only users who can ban can use it.
        This is very useful when your server is undergoing raids, unwanted attention, unwanted members, etc.
        """

    @gatekeeper.command(name="disallow", aliases=["deallow", "unallow", "unwhitelist"])
    @require_configuration()
    async def command_disallow(self, ctx: lifesaver.Context, *, user: UserReference):
        """Remove a user from the allowed users list."""
        try:
            await self.disallow_user(ctx.guild, user)
        except ValueError:
            await ctx.send(f"{ctx.tick(False)} That user isn't being allowed.")
        else:
            await ctx.send(f"{ctx.tick()} Disallowed `{user}`.")

    @gatekeeper.group(name="allow", aliases=["whitelist"], invoke_without_command=True)
    @require_configuration()
    async def group_allow(self, ctx: lifesaver.Context, *, user: UserReference):
        """Add a user to the allowed users list.

        This will add the user to the allowed_users key in the configuration,
        allowing them to bypass checks.
        """
        if self.is_being_allowed(ctx.guild, user):
            await ctx.send(f"{ctx.tick(False)} That user is already being allowed.")
            return

        await self.allow_user(ctx.guild, user)
        await ctx.send(f"{ctx.tick()} Allowed `{user}`.")

    @group_allow.command(name="temp")
    @require_configuration()
    async def command_allow_temp(
        self, ctx: lifesaver.Context, duration: int, *, user: UserReference
    ):
        """Temporarily allows a user to join for n minutes."""
        if duration > 60 * 24:
            raise commands.BadArgument("The maximum time is 1 day.")
        if duration < 1:
            raise commands.BadArgument("Invalid duration.")

        await self.allow_user(ctx.guild, user)
        minutes = pluralize(minute=duration)
        await ctx.send(f"{ctx.tick()} Temporarily allowing `{user}` for {minutes}.")

        await asyncio.sleep(duration * 60)

        try:
            await self.disallow_user(ctx.guild, user)
        except ValueError:
            # was manually removed from allowed_users... by an admin?
            pass

    @gatekeeper.command(name="lockdown", aliases=["ld"])
    @require_configuration()
    async def command_lockdown(self, ctx: lifesaver.Context, *, enabled: bool = True):
        """Enables block_all.

        You can also provide "on" or "off" to the command to manually enable
        or disable the check as desired.
        """
        async with self.edit_config(ctx.guild) as config:
            checks = config.get("checks", {})
            checks["block_all"] = {"enabled": enabled}
            config["checks"] = checks

        status = "enabled" if enabled else "disabled"
        await ctx.send(f"{ctx.tick()} `block_all` is now {status}.")

    @gatekeeper.command(name="enable", aliases=["on"])
    @require_configuration()
    async def command_enable(self, ctx: lifesaver.Context):
        """Enables Gatekeeper."""
        async with self.edit_config(ctx.guild) as config:
            config["enabled"] = True

        await ctx.send(f"{ctx.tick()} Enabled Gatekeeper.")

    @gatekeeper.command(name="disable", aliases=["off"])
    @require_configuration()
    async def command_disable(self, ctx: lifesaver.Context):
        """Disables Gatekeeper."""
        async with self.edit_config(ctx.guild) as config:
            config["enabled"] = False

        await ctx.send(f"{ctx.tick()} Disabled Gatekeeper.")

    @gatekeeper.command(name="toggle", aliases=["flip"])
    @require_configuration()
    async def command_toggle(self, ctx: lifesaver.Context):
        """Toggles Gatekeeper."""
        async with self.edit_config(ctx.guild) as config:
            config["enabled"] = not config["enabled"]

        state = "enabled" if config["enabled"] else "disabled"

        await ctx.send(f"{ctx.tick()} Gatekeeper is now {state}.")

    @gatekeeper.command(name="status")
    @require_configuration()
    async def command_status(self, ctx: lifesaver.Context):
        """Views the current status of Gatekeeper."""
        enabled = self.gatekeeper_config(ctx.guild).get("enabled", False)

        if enabled:
            description = "Incoming members must pass Gatekeeper checks to join."
        else:
            description = "Anyone can join."

        link = f"{self.dashboard_link}/guilds/{ctx.guild.id}"
        description += f"\n\nUse [the web dashboard]({link}) to configure gatekeeper."

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
