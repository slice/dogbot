import collections
from typing import List, Optional, Tuple, Type

import discord
import lifesaver
from discord.ext import commands
from lifesaver.utils import clean_mentions, escape_backticks
from lifesaver.utils.timing import Ratelimiter

from dog.converters import SoftMember
from dog.formatting import represent
from dog.utils import chained_decorators


def guild_action(**perms):
    return chained_decorators(
        [
            commands.guild_only(),
            commands.bot_has_permissions(**perms),
            commands.has_permissions(**perms),
        ]
    )


ActionVerb = collections.namedtuple("ActionVerb", ["present", "past"])


class ModAction:
    """A class that represents a mod action.

    :meth:`perform_on_user` must be overridden. It's the method that's called
    for every user that is targeted by the action. This is where the "action"
    actually happens.

    The action can be actually carried out with :meth:`perform`. That method
    automatically calls :meth:`lifesaver.Context.add_line` to add output
    messages. (:meth:`lifesaver.Context.paginate` isn't called, however.)
    """

    verb: ActionVerb = ActionVerb(present="do something", past="did something")

    def __init__(self, ctx: lifesaver.Context) -> None:
        self.ctx = ctx

    def transform_reason(self, original_reason: Optional[str]) -> Optional[str]:
        """Transform the original reason supplied by the command invoker into
        the reason to be supplied by the bot."""
        reason = f"{self.verb.past.capitalize()} by {represent(self.ctx.author)}"
        if original_reason:
            reason += f": {original_reason}"
        return reason

    async def perform_on_user(
        self, user: discord.abc.Snowflake, *, reason: Optional[str], **kwargs
    ) -> None:
        """Perform the mod action on a user, returning a message to add to the
        outputted paginator."""
        raise NotImplementedError

    async def perform(
        self, users: List[discord.abc.Snowflake], *, reason: Optional[str], **kwargs
    ) -> None:
        """Perform the mod action on a list of users."""
        reason = self.transform_reason(reason)

        for user in users:
            user_repr = represent(user)
            cant_prefix = (
                f"{self.ctx.tick(False)} Can't {self.verb.present} {user_repr}"
            )

            try:
                message = await self.perform_on_user(user, reason=reason, **kwargs)
            except discord.NotFound:
                message = f"{cant_prefix}: unknown user."
            except discord.Forbidden:
                message = f"{cant_prefix}: missing permissions."
            except discord.HTTPException as error:
                message = f"{cant_prefix}: `{error}`"
            else:
                if not message:
                    message = (
                        f"{self.ctx.tick()} {self.verb.past.capitalize()} {user_repr}."
                    )

            self.ctx.add_line(message)


class Softban(ModAction):
    verb = ActionVerb(present="softban", past="softbanned")

    async def perform_on_user(self, user, *, reason, delete_message_days: int):
        await self.ctx.guild.ban(
            user, reason=reason, delete_message_days=delete_message_days
        )
        await self.ctx.guild.unban(user, reason=reason)


class Ban(ModAction):
    verb = ActionVerb(present="ban", past="banned")

    async def perform_on_user(self, user, *, reason):
        await self.ctx.guild.ban(user, reason=reason, delete_message_days=0)


class Block(ModAction):
    verb = ActionVerb(present="block", past="blocked")

    async def perform_on_user(self, user, *, reason):
        overwrite = self.ctx.channel.overwrites_for(user)
        overwrite.read_messages = False
        await self.ctx.channel.set_permissions(user, overwrite=overwrite, reason=reason)


class Unblock(ModAction):
    verb = ActionVerb(present="unblock", past="unblocked")

    async def perform_on_user(self, user, *, reason):
        overwrite = self.ctx.channel.overwrites_for(user)
        can_read = overwrite.read_messages

        if can_read is not False:
            return f"{self.ctx.tick(False)} {represent(user)} isn't blocked from this channel."

        # neutral state
        overwrite.read_messages = None

        # if the resulting permission overwrite is empty, just delete the
        # overwrite entirely to prevent clutter.
        await self.ctx.channel.set_permissions(
            user, overwrite=None if overwrite.is_empty() else overwrite, reason=reason
        )


def mod_action_command(
    action: Type[ModAction], *, args=None, help: str = None, **perms
):
    """Generate a command that performs a :class:`ModAction`."""
    args = args or {}
    help = help or f"{action.verb.present.capitalize()} users."

    @lifesaver.command(name=action.verb.present, help=help)
    @guild_action(**perms)
    async def generated_command(
        self, ctx: lifesaver.Context, users: commands.Greedy[SoftMember], *, reason=None
    ):
        if not users:  # commands.Greedy is optional
            raise commands.UserInputError(
                f"No valid users were found to {action.verb.present}."
            )

        await action(ctx).perform(users, reason=reason, **args)
        await ctx.paginate()

    generated_command.__name__ = f"generated_mod_command_{action.verb.present}"
    return generated_command


class Mod(lifesaver.Cog):
    """Moderation-related commands."""

    def __init__(self, bot):
        super().__init__(bot)
        self.auto_cooldown = Ratelimiter(1, 3)

    ban = mod_action_command(Ban, ban_members=True)
    softban = mod_action_command(
        Softban, args=dict(delete_message_days=1), ban_members=True
    )
    block = mod_action_command(Block, manage_roles=True)
    unblock = mod_action_command(Unblock, manage_roles=True)

    @lifesaver.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return

        config = self.bot.guild_configs.get(message.guild)
        if not config:
            return
        autoresponses = config.get("autoresponses", {})

        for trigger, response in autoresponses.items():
            if trigger in message.content:
                if self.auto_cooldown.is_rate_limited(
                    message.author.id, message.channel.id
                ):
                    return
                cleaned_response = clean_mentions(message.channel, response)
                try:
                    await message.channel.send(cleaned_response)
                except discord.HTTPException:
                    pass

    @lifesaver.command()
    @guild_action(manage_roles=True)
    async def vanity(
        self,
        ctx: lifesaver.Context,
        name,
        color: discord.Color = None,
        *targets: discord.Member,
    ):
        """Creates a vanity role.

        A vanity role is a role that grants no additional permissions. This
        command is useful because creating a role in the Discord client usually
        has some unnecessary permissions prefilled.
        """
        try:
            role = await ctx.guild.create_role(
                name=name,
                color=color or discord.Color.default(),
                permissions=discord.Permissions.none(),
                reason=f"Vanity role created by {represent(ctx.author)}",
            )
        except discord.HTTPException as error:
            await ctx.send(f"{ctx.tick(False)} Failed to create vanity role: `{error}`")
            return

        name = escape_backticks(role.name)
        ctx.add_line(f"{ctx.tick()} Created vanity role `{name}`.")

        for target in targets:
            try:
                await target.add_roles(
                    role, reason=f"Vanity role auto-assign by {represent(ctx.author)}"
                )
            except discord.HTTPException as error:
                ctx.add_line(
                    f"{ctx.tick(False)} Failed to add `{name}` to {represent(target)}: `{error}`"
                )
            else:
                ctx.add_line(f"{ctx.tick()} Added `{name}` to {represent(target)}.")

        await ctx.paginate()


async def setup(bot):
    await bot.add_cog(Mod(bot))
