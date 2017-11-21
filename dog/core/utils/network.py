from io import BytesIO
from typing import Any

from aiohttp import ClientSession


async def get_bytesio(session: ClientSession, url: str) -> BytesIO:
    """
    Downloads data from a URL, and returns it as a :class:`io.BytesIO` instance.

    Parameters
    ----------
    session
        The :class:`aiohttp.ClientSession` to download with.
    url
        The URL to download.
    """
    async with session.get(url) as resp:
        return BytesIO(await resp.read())


async def get_json(session: ClientSession, url: str) -> Any:
    """
    Downloads JSON from a URL, and returns it parsed.

    Parameters
    ----------
    session
        The :class:`aiohttp.ClientSession` to download with.
    url
        The URL to download.
    """
    async with session.get(url) as resp:
        return await resp.json()
