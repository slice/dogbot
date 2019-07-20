import datetime
import logging
from typing import Optional

import discord
import lifesaver
import pytz
from discord.ext import commands
from discord.ext.commands import BucketType, cooldown
from geopy import exc as geopy_errors
from lifesaver.bot.storage import AsyncJSONStorage
from lifesaver.utils import clean_mentions
from lifesaver.utils.timing import Timer

from .converters import Timezone, hour_minute
from .geocoder import Geocoder
from .map import Map

TWELVEHOUR_COUNTRIES = ['US', 'AU', 'CA', 'PH']
UNKNOWN_LOCATION = 'Unknown location. Examples: "Arizona", "London", and "California".'

log = logging.getLogger(__name__)


class Time(lifesaver.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.geocoder = Geocoder(bot=bot, loop=bot.loop)
        self.timezones = AsyncJSONStorage('timezones.json', loop=bot.loop)

    def get_timezone_for(self, user: discord.User, *, raw: bool = False):
        timezone = self.timezones.get(user.id)
        if raw:
            return timezone

        if not timezone:
            return None
        return pytz.timezone(timezone)

    def get_time_for(self, user: discord.User) -> Optional[datetime.datetime]:
        timezone = self.get_timezone_for(user, raw=False)
        if not timezone:
            return None
        time = datetime.datetime.now(timezone)
        return time

    def get_formatted_time_for(self, user: discord.User) -> Optional[str]:
        time = self.get_time_for(user)
        if not time:
            return None

        return self.format_time(time)

    def format_time(self, time: datetime.datetime, *, shorten: bool = True, hm: bool = False) -> str:
        # omit the 12-hour representation before noon as it is redundant (both are essentially the same)
        time_format = '%H:%M' if time.hour < 12 and shorten else '%H:%M (%I:%M %p)'
        return time.strftime(time_format if hm else ('%B %d, %Y  ' + time_format))

    @lifesaver.command(aliases=['st'])
    async def sleepytime(self, ctx, *, awaken_time: hour_minute):
        """Calculates the time you should go to sleep at night."""

        cycle_length = datetime.timedelta(seconds=90 * 60)

        most_late = awaken_time - datetime.timedelta(seconds=270 * 60)
        second_time = most_late - cycle_length
        third_time = second_time - cycle_length
        fourth_time = third_time - cycle_length

        times = [fourth_time, third_time, second_time, most_late]
        time_format = '%I:%M %p'
        formatted = [f'**{time.strftime(time_format)}**' for time in times]
        await ctx.send(
            f'To wake up at {awaken_time.strftime(time_format)} feeling great, '
            f'try falling sleep at these times: {", ".join(formatted)}'
        )

    @lifesaver.group(invoke_without_command=True, aliases=['t'])
    async def time(self, ctx, *, who: discord.Member = None):
        """Views the time for another user."""
        who = who or ctx.author

        if self.bot.is_blacklisted(who):
            await ctx.send(f"{ctx.tick(False)} {who} can't use this bot.")
            return

        formatted_time = self.get_formatted_time_for(who)
        if not formatted_time:
            await ctx.send(
                (f"{ctx.tick(False)} You haven't set your timezone yet. "
                 f"Use `{ctx.prefix}time set <location>` to set it. ")
                if who == ctx.author else
                (f'{ctx.tick(False)} {who.display_name} has not set their timezone.'
                 f'They can set it with `{ctx.prefix}time set <location>`.')
            )
            return

        if ctx.guild:
            display_name = clean_mentions(ctx.channel, who.display_name)
        else:
            display_name = who.display_name
        await ctx.send(f'{display_name}: {formatted_time}')

    @time.command(aliases=['sim'])
    async def diff(self, ctx, timezone: Timezone, time: hour_minute = None):
        """View what time it is in another timezone compared to yours."""
        (source, other_tz) = timezone
        if not self.timezones.get(ctx.author.id):
            await ctx.send(f"{ctx.tick(False)} You don't have a timezone set, so you can't use this. Set one with "
                           f"`{ctx.prefix}t set`.")
            return

        if time is None:
            local_time = self.get_time_for(ctx.author)
            time = datetime.datetime(
                year=2018, month=3, day=15,
                hour=local_time.hour, minute=local_time.minute,
            )

        our_time = self.get_timezone_for(ctx.author).localize(time)
        their_time = our_time.astimezone(other_tz)
        hour_difference = min(their_time.hour - our_time.hour, our_time.hour - their_time.hour)

        possessive_source = 'in' if isinstance(source, str) else 'for'
        fmt = "There is a **{}** hour difference between you and {}.\n\nWhen it's {} for you, it would be {} {} {}."
        log.debug('A = %s, B = %s', their_time, our_time)
        await ctx.send(fmt.format(
            abs(hour_difference),
            source,
            self.format_time(our_time, hm=True),
            self.format_time(their_time, hm=True),
            possessive_source,
            source
        ))

    @time.command(typing=True, aliases=['map', 'chart'])
    @cooldown(1, 5, BucketType.guild)
    async def table(self, ctx):
        """Views a timezone chart."""

        twelve_hour = False
        try:
            invoker_timezone = self.timezones.get(ctx.author.id)
            country = next(
                country
                for (country, timezones) in pytz.country_timezones.items()
                if invoker_timezone in timezones
            )
            twelve_hour = country in TWELVEHOUR_COUNTRIES
        except StopIteration:
            pass

        map = Map(session=self.session, twelve_hour=twelve_hour, loop=self.bot.loop)

        for member in ctx.guild.members:
            tz = self.timezones.get(member.id)
            if not tz:
                continue
            map.add_member(member, tz)

        with Timer() as timer:
            await map.draw()
            buffer = await map.render()

        file = discord.File(fp=buffer, filename=f'map_{ctx.guild.id}.png')
        await ctx.send(f'Rendered in {timer}.', file=file)

        map.close()

    @time.command(name='reset')
    async def time_reset(self, ctx):
        """Resets your timezone."""
        if await ctx.confirm(title='Are you sure?', message='Your timezone will be removed.'):
            try:
                await self.timezones.delete(ctx.author.id)
            except KeyError:
                pass
            await ctx.send(f'{ctx.tick()} Done.')
        else:
            await ctx.send('Okay, cancelled.')

    @time.command(name='set', typing=True)
    @cooldown(1, 3, BucketType.user)
    async def time_set(self, ctx, *, location: commands.clean_content):
        """Sets your current timezone from location."""

        timezone = None

        if location in pytz.all_timezones:
            # If a valid timezone code is supplied, simply use the timezone
            # code. This won't account for all cases, but it should suffice.
            # Most users should be using more specific locations (NOT timezone
            # codes) anyways.
            timezone = location
        else:
            # Geolocate the timezone code.
            # Resolves a human readable location description (like "Turkey")
            # into its timezone code (like "Europe/Istanbul").
            try:
                location = await self.geocoder.geocode(location)
                if location is None:
                    await ctx.send(f'{ctx.tick(False)} {UNKNOWN_LOCATION}')
                    return

                timezone = await self.geocoder.timezone(location.point)
                if timezone is None:
                    await ctx.send(f'{ctx.tick(False)} {UNKNOWN_LOCATION}')
                    return
            except geopy_errors.GeocoderQuotaExceeded:
                await ctx.send(f"{ctx.tick(False)} I can't locate you. Please try again later.")
                return
            except geopy_errors.GeopyError as error:
                await ctx.send(f"{ctx.tick(False)} I can't find your location: `{error}`")
                return

        await self.timezones.put(ctx.author.id, str(timezone))

        time = self.get_time_for(ctx.author)
        greeting = 'Good evening!'

        if 5 < time.hour < 13:
            greeting = 'Good morning!'
        elif 13 <= time.hour < 19:
            greeting = 'Good afternoon!'

        await ctx.send(f'{ctx.tick()} Your timezone is now set to `{timezone}`. {greeting}')
