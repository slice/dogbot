import datetime
import logging
import typing as T

import discord
import lifesaver
import dateutil.tz
from discord.ext import commands
from discord.ext.commands import BucketType, cooldown
from geopy import exc as geopy_errors
from lifesaver.bot.storage import AsyncJSONStorage
from lifesaver.utils import clean_mentions
from lifesaver.utils.timing import Timer

from . import messages
from .formatting import format_dt, greeting
from .converters import Timezone, hour_minute
from .resolver import Resolver
from .map import Map
from .messages import (
    QUOTA_EXCEEDED,
    NO_AUTHOR_TIMEZONE,
    NO_TARGET_TIMEZONE,
    NO_TIMEZONE_SO_NO_COMMAND,
    DEPRECATED_TIMEZONE,
    DIFFERENCE,
)

# These timezones are deprecated in the tz database and most do not account
# for DST properly. A more specific zone should be chosen instead.
DEPRECATED_TIMEZONES = {
    "CET",  # Central European Time
    "EET",  # Eastern European Time
    "HST",  # Hawaiian Standard Time
    "RST",  # Romance Standard Time
    "MET",  # Middle Eastern Time
    "MST",  # Mountain Time Zone
    "PST",  # Pacific Standard Time
    "PDT",  # Pacific Daylight Time
    "EST",  # Eastern Standard Time
    "EDT",  # Eastern Daylight Time
    "CST",  # Central Standard Time
    "CDT",  # Central Daylight Time
}

log = logging.getLogger(__name__)


class Time(lifesaver.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.resolver = Resolver(bot=bot, loop=bot.loop)
        self.timezones = AsyncJSONStorage("timezones.json", loop=bot.loop)

    def get_timezone_for(self, user: discord.abc.User) -> T.Optional[datetime.tzinfo]:
        """Return a user's timezone as a :class:`datetime.tzinfo`."""
        timezone = self.timezones.get(user.id)

        if not timezone:
            return None

        return dateutil.tz.gettz(timezone)

    def get_time_for(self, user: discord.abc.User) -> T.Optional[datetime.datetime]:
        """Return the current :class:`datetime.datetime` for a user.

        If they have no timezone, then ``None`` is returned.
        """
        timezone = self.get_timezone_for(user)

        if not timezone:
            return None

        return datetime.datetime.now(tz=timezone)

    def get_formatted_time_for(
        self, user: discord.abc.User, **kwargs
    ) -> T.Optional[str]:
        """Return the formatted time for a user."""
        time = self.get_time_for(user)

        if not time:
            return None

        return format_dt(time, **kwargs)

    @lifesaver.command(aliases=["st"])
    async def sleepytime(self, ctx, *, awaken_time: hour_minute):
        """Calculates the time you should go to sleep at night."""

        cycle_length = datetime.timedelta(seconds=90 * 60)

        most_late = awaken_time - datetime.timedelta(seconds=270 * 60)
        second_time = most_late - cycle_length
        third_time = second_time - cycle_length
        fourth_time = third_time - cycle_length

        times = [fourth_time, third_time, second_time, most_late]
        time_format = "%I:%M %p"
        formatted = [f"**{time.strftime(time_format)}**" for time in times]
        await ctx.send(
            f"To wake up at {awaken_time.strftime(time_format)} feeling great, "
            f'try falling sleep at these times: {", ".join(formatted)}'
        )

    @lifesaver.group(invoke_without_command=True, aliases=["t"])
    async def time(self, ctx, *, who: discord.Member = None):
        """Views the time for another user."""
        who = who or ctx.author

        if self.bot.is_blacklisted(who):
            await ctx.send(f"{ctx.tick(False)} {who} can't use this bot.")
            return

        formatted_time = self.get_formatted_time_for(who)
        if not formatted_time:
            await ctx.send(
                f"{ctx.tick(False)} "
                + (
                    NO_AUTHOR_TIMEZONE.format(prefix=ctx.prefix)
                    if who == ctx.author
                    else NO_TARGET_TIMEZONE.format(other=who, prefix=ctx.prefix)
                )
            )
            return

        if ctx.guild:
            display_name = clean_mentions(ctx.channel, who.display_name)
        else:
            display_name = who.display_name
        await ctx.send(f"{display_name}: {formatted_time}")

    @time.command()
    async def diff(self, ctx, timezone: Timezone, time: hour_minute = None):
        """View what time it is in another timezone compared to yours."""
        (source, other_tz) = timezone

        if not self.timezones.get(ctx.author.id):
            await ctx.send(
                f"{ctx.tick(False)} "
                + NO_TIMEZONE_SO_NO_COMMAND.format(prefix=ctx.prefix)
            )
            return

        if time is not None:
            # The ``hour_minute`` converter returns a naive ``datetime.datetime``,
            # so we inject the user's timezone here. We don't use ``astimezone``
            # because the user is specifying the time as if it was in their timezone.
            time = time.replace(tzinfo=self.get_timezone_for(ctx.author))

        our_time = time or self.get_time_for(ctx.author)
        assert our_time is not None
        their_time = our_time.astimezone(other_tz)

        one_hour = datetime.timedelta(hours=1)
        assert one_hour is not None

        our_utc_offset = our_time.utcoffset()
        assert our_utc_offset is not None
        our_utc_offset_hours = our_utc_offset / one_hour

        their_utc_offset = their_time.utcoffset()
        assert their_utc_offset is not None
        their_utc_offset_hours = their_utc_offset / one_hour

        hour_difference = abs(our_utc_offset_hours - their_utc_offset_hours)
        if hour_difference.is_integer():
            # Cast to an ``int`` if it's ``.0``.
            hour_difference = int(hour_difference)

        await ctx.send(
            DIFFERENCE.format(
                source=source,
                difference=hour_difference,
                our_time=format_dt(our_time, time_only=True, include_postscript=False),
                their_time=format_dt(
                    their_time, time_only=True, include_postscript=False
                ),
                possessive="in" if isinstance(source, str) else "for",
            )
        )

    @time.command(typing=True, aliases=["map", "chart"])
    @cooldown(1, 5, BucketType.guild)
    async def table(self, ctx):
        """Views a timezone chart."""

        map = Map(session=self.session, twelve_hour=False, loop=self.bot.loop)

        for member in ctx.guild.members:
            tz = self.timezones.get(member.id)
            if not tz:
                continue
            map.add_member(member, tz)

        with Timer() as timer:
            await map.draw()
            buffer = await map.render()

        file = discord.File(fp=buffer, filename=f"map_{ctx.guild.id}.png")
        await ctx.send(f"Rendered in {timer}.", file=file)

        map.close()

    @time.command(name="reset")
    async def time_reset(self, ctx):
        """Resets your timezone."""
        if await ctx.confirm(
            title="Are you sure?", message="Your timezone will be removed."
        ):
            try:
                await self.timezones.delete(ctx.author.id)
            except KeyError:
                pass
            await ctx.send(f"{ctx.tick()} Your timezone was removed.")
        else:
            await ctx.send("Operation cancelled.")

    @time.command(name="set")
    @cooldown(1, 2, BucketType.user)
    async def time_set(
        self,
        ctx: lifesaver.Context,
        *,
        location: str = commands.parameter(
            converter=commands.clean_content,
            description="your current location",
            displayed_default="New York",
        ),
    ):
        """Sets your timezone.

        The location you provide will be resolved into a timezone through
        geocoding. You can type the name of a country, state, city, region, etc.

        You may also directly provide a timezone code according to the "tz
        database", also known as "tzdata", "zoneinfo", "IANA time zone
        database", and the "Olson database". In this case, no geocoding will
        be performed. For a list of all timezones in the tz database, see:

            https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List

        Providing a direct UTC offset is also possible, but is discouraged as
        DST will not be handled--you are simply providing a hard offset from
        UTC.

        Examples:

        time set Berlin
        time set London
        time set California
        time set Arizona
            Sets your timezone to the geocoded timezone of that named region.
            Ensure that the location you are giving has an unambiguous timezone
            (e.g., do not simply specify "US" as there are multiple timezones
            in the United States).

        time set Europe/Berlin
        time set Europe/London
        time set America/Los_Angeles
        time set America/Phoenix
            Sets your timezone according to the timezone name. The offset
            information is pulled directly from the tz database.

        time set UTC+1
        time set UTC
        time set UTC-8
        time set UTC-7
            Sets your timezone according to the UTC offset. DST will not be
            handled for you.
        """

        if location in DEPRECATED_TIMEZONES:
            # Prevent the usage of deprecated timezones that don't handle
            # daylight saving correctly.
            await ctx.send(
                f"{ctx.tick(False)} " + DEPRECATED_TIMEZONE.format(prefix=ctx.prefix)
            )
            return

        failed_message = f"{ctx.tick(False)} {messages.UNKNOWN_LOCATION}".format(prefix=ctx.prefix)  # fmt: skip

        try:
            resolution = await self.resolver.resolve_timezone(location)

            if resolution is None:
                await ctx.send(failed_message)
                return
        except geopy_errors.GeocoderQuotaExceeded:
            await ctx.send(QUOTA_EXCEEDED)
            return
        except geopy_errors.GeopyError:
            self.log.exception("failed to geolocate")
            await ctx.send(failed_message)
            return

        await self.timezones.put(ctx.author.id, str(resolution.timezone))

        time = self.get_time_for(ctx.author)
        assert time is not None

        formatted_time = format_dt(time, time_only=True, include_postscript=False)
        appropriate_greeting = greeting(time)

        if ctx.can_send_embeds:
            message = messages.TIMEZONE_SAVED_EMBED.format(prefix=ctx.prefix)
            embed = discord.Embed(
                title=f"{appropriate_greeting} It's {formatted_time}.",
                color=discord.Color.green(),
                description=message,
            )
            if resolution.did_geolocate:
                embed.set_footer(text=messages.OPENSTREETMAP_ATTRIBUTION)
            await ctx.send(embed=embed)
        else:
            message = messages.TIMEZONE_SAVED.format(
                time=formatted_time, prefix=ctx.prefix
            )
            await ctx.send(
                f"{ctx.tick()} {appropriate_greeting}\n\n{message}\n\n"
                + messages.OPENSTREETMAP_ATTRIBUTION
            )
