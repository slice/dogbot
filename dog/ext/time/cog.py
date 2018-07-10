import datetime
import logging
from typing import Optional

import discord
import pytz
from discord.ext import commands
from discord.ext.commands import BucketType, cooldown
from lifesaver.bot import Cog, Context, command, group
from lifesaver.bot.storage import AsyncJSONStorage
from geopy import exc as geopy_errors

from .converters import hour_minute
from .geocoder import Geocoder
from .map import Map

log = logging.getLogger(__name__)


def timezone_is_concrete(timezone: str) -> bool:
    tz = pytz.timezone(timezone)
    return isinstance(tz, pytz.tzinfo.StaticTzInfo)


TWELVEHOUR_COUNTRIES = ['US', 'AU', 'CA', 'PH']


class Time(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.geocoder = Geocoder(bot=bot, loop=bot.loop)
        self.timezones = AsyncJSONStorage('timezones.json', loop=bot.loop)

    def get_time_for(self, user: discord.User) -> Optional[datetime.datetime]:
        timezone = self.timezones.get(user.id)
        if not timezone:
            return None
        time = datetime.datetime.now(pytz.timezone(timezone))
        return time

    def get_formatted_time_for(self, user: discord.User) -> Optional[str]:
        time = self.get_time_for(user)
        if not time:
            return None

        # omit the 12-hour representation before noon as it is redundant (both are essentially the same)
        time_format = '%H:%M:%S' if time.hour < 12 else '%H:%M:%S (%I:%M:%S %p)'
        return time.strftime('%B %d, %Y  ' + time_format)

    @command(aliases=['st'])
    async def sleepytime(self, ctx: Context, *, awaken_time: hour_minute):
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

    @group(invoke_without_command=True, aliases=['t'])
    async def time(self, ctx: Context, *, who: discord.Member = None):
        """Views the time for another user."""
        who = who or ctx.author

        if self.bot.is_blacklisted(who):
            await ctx.send(f"{who} can't use this bot.")
            return

        formatted_time = self.get_formatted_time_for(who)
        if not formatted_time:
            await ctx.send(
                f"\U00002753 You haven't set your timezone yet. Use `{ctx.prefix}time set <location>` to set it."
                if who == ctx.author else
                (f'\U00002753 {who.display_name} has not set their timezone. They can set their timezone with '
                 f'`{ctx.prefix}time set`, like: `{ctx.prefix}time set London`.')
            )
            return

        await ctx.send(f'{who.display_name}: {formatted_time}')

    @time.command(typing=True)
    @cooldown(1, 5, BucketType.guild)
    async def map(self, ctx: Context):
        """Views a timezone map."""

        twelve_hour = False
        try:
            invoker_timezone = self.timezones.get(ctx.author.id)
            country = next(
                country for (country, timezones) in pytz.country_timezones.items() if invoker_timezone in timezones
            )
            twelve_hour = country in TWELVEHOUR_COUNTRIES
        except StopIteration:
            pass

        map = Map(session=self.bot.session, twelve_hour=twelve_hour, loop=self.bot.loop)

        for member in ctx.guild.members:
            tz = self.timezones.get(member.id)
            if not tz:
                continue
            map.add_member(member, tz)

        await map.draw()
        buffer = await map.render()

        file = discord.File(fp=buffer, filename=f'map_{ctx.guild.id}.png')
        await ctx.send(file=file)

        map.close()

    @time.command(name='reset')
    async def time_reset(self, ctx: Context):
        """Resets your timezone."""
        if await ctx.confirm(title='Are you sure?', message='Your timezone will be removed.'):
            try:
                await self.timezones.delete(ctx.author.id)
            except KeyError:
                pass
            await ctx.send('Done.')
        else:
            await ctx.send('Okay, cancelled.')

    @time.command(name='set', typing=True)
    @cooldown(1, 3, BucketType.user)
    async def time_set(self, ctx: Context, *, location: commands.clean_content):
        """Sets your current timezone from location."""

        timezone = None
        try:
            location = await self.geocoder.geocode(location)
            if location is None:
                await ctx.send('\U00002753 Unknown location. Examples: "Arizona", "London", "California"')
                return

            timezone = await self.geocoder.timezone(location.point)
        except geopy_errors.GeocoderQuotaExceeded:
            await ctx.send('\U0001f6b1 API quota exceeded, please try again later.')
        except geopy_errors.GeopyError as error:
            await ctx.send(f'\U00002753 Unable to resolve your location: `{error}`')

        await self.timezones.put(ctx.author.id, str(timezone))

        time = self.get_time_for(ctx.author)
        greeting = 'Good evening!'

        if 5 < time.hour < 13:
            greeting = 'Good morning!'
        elif 13 <= time.hour < 19:
            greeting = 'Good afternoon!'

        await ctx.send(
            f'\N{OK HAND SIGN} Your timezone is now set to {timezone}. {greeting}'
        )
