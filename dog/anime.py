""" Utilities for searching for anime on MAL. """

import logging
import xml.etree.ElementTree as ET
from collections import namedtuple

import aiohttp

from dog.core import utils

logger = logging.getLogger(__name__)

MAL_SEARCH = 'https://myanimelist.net/api/anime/search.xml?q='


class Anime(namedtuple('Anime', ('id title english synonyms episodes score type'
                                 ' status start_date end_date synopsis image'))):
    """ Represents an Anime on MyAnimeList. """
    def __str__(self):
        english = ' ({0.english})'.format(self) if self.english is not None else ''
        return '{0.title}{1}, {0.episodes} episode(s)'.format(self, english)


async def anime_search(bot, query: str):
    """ Searches for anime on MyAnimeList. Returns a list of `Anime` instances. """
    mal_auth = bot.cfg['credentials']['myanimelist']
    auth = aiohttp.BasicAuth(mal_auth['username'], mal_auth['password'])
    query_url = utils.urlescape(query)
    results = []
    try:
        async with bot.session.get(MAL_SEARCH + query_url, auth=auth) as resp:
            tree = ET.fromstring(await resp.text())
            for anime_tag in tree.findall('entry'):
                results.append(Anime(**{a.tag: a.text for a in list(anime_tag)}))
    except aiohttp.ClientResponseError:
        logger.info('Found no anime for %s', query)
        return
    return results
