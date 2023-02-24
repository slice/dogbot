import asyncio
import collections.abc
import logging
import typing as T

import discord
from lifesaver.utils.timing import Ratelimiter

from dog.formatting import represent

from . import checks as checks_module
from .core import Ban, Bounce, CheckFailure, Report, create_embed
from .threshold import Threshold

ALL_CHECKS = [getattr(checks_module, name) for name in checks_module.__all__]

INCORRECTLY_CONFIGURED_STRING = """**Gatekeeper was configured incorrectly!**

I'm not sure what to do, so I'm going to prevent this user from joining just to
be safe."""


class Keeper:
    """A class that gatekeeps users from guilds by processing checks and
    ratelimits on users.

    Each :class:`discord.Guild` should have its own persistent Keeper instance.
    This class tracks some state in order to handle ratelimits and take
    associated action.

    The Gatekeeper cog automatically handles Keeper creation. Keepers are also
    stored in its state. Keepers hold the Gatekeeper configuration
    (NOT the entire guild configuration). Whenever a guild configuration is
    updated, the Gatekeeper cog updates the configuration for that guild's
    Keeper instance (if it has one).
    """

    def __init__(self, guild: discord.Guild, config, *, bot) -> None:
        self.bot = bot
        self.guild = guild
        self.log = logging.getLogger(f"{__name__}[{guild.id}]")

        #: A list of recent :class:`discord.Member`s that have joined. This list
        #: is used to keep track of users joining so that during a burst of
        #: joins (like in a raid), everyone who joined is removed instead of the
        #: single user that ended up triggering the ratelimit.
        self.recent_joins: T.List[discord.Member] = []

        #: The Gatekeeper config (the ``gatekeeper`` key of the guild config).
        self.config: T.Optional[T.Dict] = None

        #: A ratelimiter for each user. Combats users repeatedly joining after
        #: being bounced by Gatekeeper.
        self.unique_join_ratelimiter: T.Optional[Ratelimiter] = None

        #: A ratelimiter for all users. Combats large amounts of users joining
        #: at a time (like in raids).
        self.join_ratelimiter: T.Optional[Ratelimiter] = None

        self.update_config(config)

    def __repr__(self):
        return f"<Keeper guild={self.guild!r}>"

    @property
    def broadcast_channel(self) -> discord.TextChannel:
        """Return the broadcast channel for the associated guild."""
        channel_id = self.config.get("broadcast_channel")
        if channel_id is None:
            return None

        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return None

        return channel

    @property
    def bounce_message(self):
        """Return the configured bounce message."""
        return self.config.get("bounce_message")

    def _update_ratelimiter(
        self,
        threshold: T.Optional[str],
        attribute_name: str,
        *,
        after_update: T.Callable[[Ratelimiter, Ratelimiter], None] = None,
    ):
        """Update/create a :class:`Ratelimiter` attribute on ``self`` using a
        threshold string and attribute name.

        The :class:`Ratelimiter` is created from the provided threshold string.
        ``self`` is updated using the given ``attribute_name``. If the
        ratelimiter hasn't changed, then the old one will be kept.

        If the threshold string contains invalid syntax or is ``None``,
        the ratelimiter attribute becomes disabled.
        """

        try:
            if threshold is None:
                raise TypeError

            old_ratelimiter = getattr(self, attribute_name)

            threshold = Threshold.from_string(threshold)
            new_ratelimiter = Ratelimiter(threshold.rate, threshold.per)

            if old_ratelimiter != new_ratelimiter:
                setattr(self, attribute_name, new_ratelimiter)
                self.log.debug(
                    "_update_ratelimiter: replacing stale ratelimiter %s",
                    attribute_name,
                )

                if after_update:
                    after_update(old_ratelimiter, new_ratelimiter)
            else:
                self.log.debug(
                    "_update_ratelimiter: not stale, using old %s", attribute_name
                )
        except TypeError:
            self.log.debug("_update_ratelimiter: invalid %s, disabling", attribute_name)
            setattr(self, attribute_name, None)

    def update_config(self, config):
        """Update this Keeper to use a new config."""
        self.config = config

        # this method can be indirectly called by _lockdown. it edits the config
        # which in turn makes the Gatekeeper cog call this method. so, we need
        # to make sure that our ratelimits don't reset!
        #
        # the special _update_ratelimiter doesn't reset ratelimits if the new
        # config doesn't change that ratelimit.

        self._update_ratelimiter(config.get("ban_threshold"), "unique_join_ratelimiter")

        def remove_unneeded_joins(old, new):
            if old is None:
                # join_ratelimiter is being created for the first time
                return

            if new.rate < old.rate:
                num_outside = old.rate - new.rate
                self.log.debug(
                    "update_config: removing %d outside tracked joins", num_outside
                )
                del self.recent_joins[:num_outside]

        auto_lockdown = config.get("auto_lockdown", {})
        auto_lockdown_threshold = auto_lockdown.get("threshold")

        self._update_ratelimiter(
            auto_lockdown_threshold,
            "join_ratelimiter",
            after_update=remove_unneeded_joins,
        )

    async def _lockdown(self):
        """Enable the block_all check for this guild and send a warning report."""
        gatekeeper_cog = self.bot.get_cog("Gatekeeper")
        async with gatekeeper_cog.edit_config(self.guild) as config:
            config["checks"] = {
                **config.get("checks", {}),
                "block_all": {"enabled": True},
            }

        # TODO: have this be reported in a separate channel, with a mod ping!
        await self.report(
            "Users are joining too quickly. `block_all` has automatically been enabled."
        )

    async def _auto_lockdown(self, triggering_member):
        """Start the auto lockdown procedure."""
        # triggering_member is the user that joined that ended up causing the
        # ratelimiter to go off. now we have to remove this user...
        await self.bounce(triggering_member, "Users are joining too quickly")

        # ...and the rest of the users who were part of the join burst.
        #
        # we explicitly filter out the triggering member because if they joined
        # more than once to trigger the ratelimit, they would appear in this
        # list.
        accompanying = [
            member
            for member in self.recent_joins[-self.join_ratelimiter.rate :]
            if member != triggering_member
        ]

        self.log.debug("_auto_lockdown: triggering_member: %r", triggering_member)
        self.log.debug("_auto_lockdown: accompanying: %r", accompanying)

        if accompanying:
            for member in accompanying:
                await self.bounce(member, "Users are joining too quickly")

        # empty out the recent joins list
        self.recent_joins = []

        checks = self.config.get("checks", {})
        block_all_check = checks.get("block_all", {})
        is_blocking_all = block_all_check.get("enabled", False)

        # now prevent anyone else from joining by enabling block_all
        if not is_blocking_all:
            self.log.debug("performing automatic lockdown")
            await self._lockdown()
        else:
            self.log.debug("already blocking all, skipping lockdown")

    async def send_bounce_message(self, member: discord.Member):
        """Send a bounce message to a member."""
        if self.bounce_message is None:
            return

        try:
            await member.send(self.bounce_message)
        except discord.HTTPException:
            if self.config.get("echo_dm_failures", False):
                await self.report(
                    f"Failed to send bounce message to {represent(member)}."
                )

    async def report(self, *args, **kwargs) -> T.Optional[discord.Message]:
        """Send a message to the designated broadcast channel of a guild.

        If the bot doesn't have permission to send to the channel, the error
        will be silently dropped.
        """
        channel = self.broadcast_channel

        if not channel:
            self.log.warning("no broadcast channel, cannot report")
            return

        if channel.guild != self.guild:
            self.log.warning("broadcast channel is somewhere else, ignoring")
            return

        try:
            return await channel.send(*args, **kwargs)
        except discord.HTTPException as error:
            self.log.warning("unable to send message to %r: %r", channel, error)

    async def _ban_reverse_prompt(
        self, message: discord.Message, banned: discord.Member
    ):
        """Shows a reaction prompt to reverse a ban.

        This is only called on ban notice messages to let moderators reverse an
        automatic ban.
        """
        unban_emoji = self.bot.emoji("gatekeeper.unban")
        await message.add_reaction(unban_emoji)

        def check(reaction, member):
            if not isinstance(member, discord.Member) or member.bot:
                return False
            can_ban = member.guild_permissions.ban_members
            return (
                reaction.message.id == message.id
                and reaction.emoji == unban_emoji
                and can_ban
            )

        _reaction, user = await self.bot.wait_for("reaction_add", check=check)

        try:
            await banned.unban(
                reason=f"Gatekeeper: Ban was reversed by {represent(user)}"
            )
        except discord.HTTPException as error:
            await self.report(
                f"Cannot reverse the ban of {represent(banned)}: `{error}`"
            )
        else:
            await self.report(
                f"The ban of {represent(banned)} was reversed by {represent(user)}."
            )

    async def ban(self, member: discord.Member, reason: str):
        """Ban a user from the guild.

        An embed with the provided ban reason will be reported to the guild's
        broadcast channel.
        """
        try:
            # cya nerd
            await member.ban(delete_message_days=0, reason=f"Gatekeeper: {reason}")
        except discord.HTTPException as error:
            self.log.debug("failed to ban %d: %r", member.id, error)
            await self.report(f"Failed to ban {represent(member)}: `{error}`")
        else:
            embed = create_embed(
                member,
                color=discord.Color.purple(),
                title=f"Banned {represent(member)}",
                reason=reason,
            )
            message = await self.report(embed=embed)
            # in case mods wants to reverse the ban, present a reaction prompt
            self.bot.loop.create_task(self._ban_reverse_prompt(message, member))

    async def bounce(self, member: discord.Member, reason: str):
        """Kick ("bounce") a user from the guild.

        An embed with the provided bounce reason will be reported to the guild's
        broadcast channel.
        """
        await self.send_bounce_message(member)

        try:
            await member.kick(reason=f"Gatekeeper: {reason}")
        except discord.HTTPException as error:
            self.log.debug("failed to kick %d: %r", member.id, error)
            await self.report(f"Failed to kick {represent(member)}: `{error}`")
        else:
            embed = create_embed(
                member,
                color=discord.Color.red(),
                title=f"Bounced {represent(member)}",
                reason=reason,
            )
            await self.report(embed=embed)

    async def _perform_checks(self, member: discord.Member, checks):
        """Perform a list of checks on a member.

        When calling this method, make sure to handle any thrown Report, Ban,
        and Bounce exceptions.
        """
        for check in ALL_CHECKS:
            check_name = check.__name__
            check_options = checks.get(check_name)

            # check isn't present in the config
            if check_options is None:
                continue

            if isinstance(check_options, collections.abc.Mapping):
                # enabled subkey of check options
                if not check_options.get("enabled", False):
                    continue
            elif isinstance(check_options, bool):
                # legacy behavior: the "check options" is simply a boolean
                # denoting whether the check is enabled or not
                if not check_options:
                    continue

            try:
                await check(member, check_options)
            except CheckFailure as error:
                # inject check details into the error
                error.check_name = check_name
                error.check = check
                raise error from None

    async def _unique_joining_too_quickly_ban(self, member: discord.Member):
        self.log.debug("%d: is joining too quickly, banning", member.id)
        await self.ban(member, "Joining too quickly")

        if not self.config.get("ban_threshold_auto_unban", True):
            return

        async def automatic_unban_task():
            ban_period = self.config.get("ban_threshold_auto_unban_after", 300)
            await asyncio.sleep(ban_period)

            try:
                await member.guild.fetch_ban(member)
            except discord.HTTPException:
                # already unbanned, or can't unban anymore
                return

            try:
                await member.unban(
                    reason=f"Gatekeeper: Automatically unbanned after {ban_period} second(s) (was joining too quickly)"
                )
            except discord.HTTPException as error:
                await self.report(
                    f"Failed to automatically unban {represent(member)} after "
                    f"{ban_period} second(s) for joining too quickly: `{error}`"
                )
            else:
                await self.report(
                    f"Automatically unbanned {represent(member)} "
                    f"after {ban_period} second(s) for joining too quickly."
                )

        self.bot.loop.create_task(automatic_unban_task())

    async def check(self, member: discord.Member) -> bool:
        """Perform checks on a member and bounce or ban them if necessary.

        Ratelimits (thresholds) are also checked in this method.
        """
        self.log.debug("%d: gatekeeping! (created_at=%s)", member.id, member.created_at)

        if self.unique_join_ratelimiter and self.unique_join_ratelimiter.hit(member.id):
            # user is joining too fast!
            await self._unique_joining_too_quickly_ban(member)
            return False

        async def handle_misconfiguration(report):
            self.log.debug("error in config: %r", report)
            await self.report(str(report))
            await self.bounce(member, INCORRECTLY_CONFIGURED_STRING)

        # perform bannable checks
        try:
            bannable_checks = self.config.get("bannable_checks", {})
            await self._perform_checks(member, bannable_checks)
        except CheckFailure as error:
            self.log.debug(
                '%d: banning, failed to pass bannable checks (failed "%s", err=%r)',
                member.id,
                error.check_name,
                error,
            )
            await self.ban(member, str(error))
            return False
        except Report as report:
            await handle_misconfiguration(report)
            return False

        # perform regular checks
        try:
            enabled_checks = self.config.get("checks", {})
            await self._perform_checks(member, enabled_checks)
        except Ban as ban:
            self.log.debug("%d: banning (err=%r)", member.id, ban)
            await self.ban(member, str(ban))
            return False
        except Bounce as bounce:
            self.log.debug(
                '%d: failed to pass "%s" (err=%r)', member.id, bounce.check_name, bounce
            )
            await self.bounce(member, str(bounce))
            return False
        except Report as report:
            await handle_misconfiguration(report)
            return False

        if self.join_ratelimiter and self.join_ratelimiter.hit():
            # users are joining too fast!
            self.log.debug("users are joining too quickly")
            await self._auto_lockdown(member)
            return False

        # prevent this list from growing too large
        # TODO: we should just check if the join ratelimiter has expired and
        #       empty the list if so
        if self.join_ratelimiter:
            if len(self.recent_joins) >= self.join_ratelimiter.rate + 5:
                self.recent_joins.pop(0)
            self.recent_joins.append(member)

        self.log.debug("%d: passed all checks", member.id)
        return True
