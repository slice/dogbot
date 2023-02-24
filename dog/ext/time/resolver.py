__all__ = ("Location", "Resolver")

import asyncio
import functools
from typing import NamedTuple, cast, Optional
from lifesaver.utils import Ratelimiter
from timezonefinder import TimezoneFinder
import logging
import zoneinfo
from contextlib import suppress

import geopy

from dog.bot import Dogbot


class Location(NamedTuple):
    latitude: float
    longitude: float


class TimezoneResolution(NamedTuple):
    timezone: str
    did_geolocate: bool
    location: Optional[Location]


class Resolver:
    def __init__(self, *, bot: Dogbot, loop: asyncio.AbstractEventLoop) -> None:
        self.client = geopy.Nominatim(user_agent="dogbot/0.0.0 (https://slice.zone)")
        self.timezone_finder = TimezoneFinder()
        # OpenStreetMap enforces a maximum of 1 request per second, but let's
        # be even more safe (and polite!)
        self.ratelimiter = Ratelimiter(rate=1, per=3)
        self.bot = bot
        self.loop = loop
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)

    async def geocode(self, query: str) -> Optional[Location]:
        """Resolve the coordinates of a location as indicated by a human-friendly place name."""
        self.log.info("geocoding: %r", query)

        if self.ratelimiter.hit():
            remaining_time = self.ratelimiter.remaining_time(True)
            self.log.debug("hit ratelimit, sleeping for %f", remaining_time)
            await asyncio.sleep(remaining_time)

        geocode_partial = functools.partial(self.client.geocode, query, exactly_one=True)  # fmt: skip
        location = cast(geopy.Location, await self.loop.run_in_executor(None, geocode_partial))  # fmt: skip

        if not location:
            return None

        self.log.debug("resolved %r to %r", query, location)
        return Location(latitude=location.latitude, longitude=location.longitude)

    async def timezone(self, location: Location) -> Optional[str]:
        """Look up the timezone appropriate for a location."""
        lookup_partial = functools.partial(
            self.timezone_finder.timezone_at,
            lng=location.longitude,
            lat=location.latitude,
        )
        return await self.loop.run_in_executor(None, lookup_partial)

    async def resolve_timezone(self, query: str) -> Optional[TimezoneResolution]:
        """Try to resolve a human-friendly place name into its corresponding timezone.

        If a IANA timezone code is provided, it is used directly.
        """

        with suppress(zoneinfo.ZoneInfoNotFoundError):
            zoneinfo.ZoneInfo(query)
            self.log.info("resolved from a timezone code: %r", query)
            return TimezoneResolution(
                timezone=query, did_geolocate=False, location=None
            )

        resolved_location = await self.geocode(query)
        if resolved_location is None:
            return None

        timezone = await self.timezone(resolved_location)
        if timezone is None:
            return None

        return TimezoneResolution(
            timezone=timezone, did_geolocate=True, location=resolved_location
        )
