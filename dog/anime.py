""" Utilities for searching for anime on MAL. """

import logging
import xml.etree.ElementTree as ET
from collections import namedtuple
from typing import List

import aiohttp

from dog.core import utils
from dog_config import myanimelist

logger = logging.getLogger(__name__)

MAL_SEARCH = 'https://myanimelist.net/api/anime/search.xml?q='

Anime = namedtuple('Anime', ('id title english synonyms episodes score type'
                             ' status start_date end_date synopsis image'))
""""""


async def anime_search(query: str) -> List[Anime]:
    """ Searches for anime on MyAnimeList. Returns a list of `Anime` instances. """
    auth = aiohttp.BasicAuth(myanimelist['username'], myanimelist['password'])
    query_url = utils.urlescape(query)
    results = []
    with aiohttp.ClientSession(auth=auth) as session:
        try:
            async with session.get(MAL_SEARCH + query_url) as resp:
                tree = ET.fromstring(await resp.text())
                for anime_tag in tree.findall('entry'):
                    results.append(Anime(**{a.tag: a.text for a in
                                            list(anime_tag)}))
        except aiohttp.ClientResponseError:
            logger.info('Found no anime for %s', query)
            return None
    return results
