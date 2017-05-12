Supplemental
------------

These modules are supplemental are not required for core Dogbot functionality.
They also don't have their own package *yet*.

`dog.humantime`
===============

.. automodule:: dog.humantime
  :members:

`dog.ext.stats`
===========

.. NOTE::
   Although this is an extension, it has been included because it contains some handy module-level
   functions.

.. automodule:: dog.ext.stats
  :members:

`dog.haste`
===========

.. automodule:: dog.haste
  :members:

`dog.anime` 
===========

.. automodule:: dog.anime
  :members: anime_search

.. class:: Anime

   Represents an Anime on MyAnimeList.

  .. attribute:: end_date

    The date the series has stopped airing.

  .. attribute:: episodes

    The amount of episodes the series has.

  .. attribute:: id

    The ID of the series.

  .. attribute:: image

    A URL to an image of the series.

  .. attribute:: english

    The `title` of the series, in English.

  .. attribute:: score

    The score of the series.

  .. attribute:: start_date

    The date the series has started airing.

  .. attribute:: status

    The status of the airing status of the series.

  .. attribute:: synonyms

    Additional or alternative names for the series.

  .. attribute:: synopsis

    Synopsis of the series.

  .. attribute:: title

    The title of the series.

  .. attribute:: type

    The type of the series.
