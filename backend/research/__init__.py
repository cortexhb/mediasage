"""External research: what the world says about an album.

Four sources behind one pipeline, each in a module of its own:

  models.py       what the APIs answer, parsed once per shape
  http.py         SharedHttp and Throttle, the client and the rate limit
  musicbrainz.py  MusicBrainz: finding the album, then reading it
  wikipedia.py    the article, minus the sections a pitch cannot use
  covers.py       Cover Art Archive: front cover for an album Plex has none for
  reviews.py      critical reviews, read off whatever page is linked
  safety.py       SafeFetcher: whether a URL may be fetched, hop by hop
  album.py        AlbumResearch, the pipeline the application talks through

Every fetch that follows a third party's link goes through `SafeFetcher`: the
URLs are curated by MusicBrainz, but they still point at someone else's server.

Nothing here raises. A source that fails contributes nothing and the pitch it
would have grounded says less; losing an album over a slow review site would
be worse than an unsourced sentence.

`backend.recommender` owns `ResearchData`, the shape this fills in: it is what
a pitch is written from, so it belongs to the pipeline that writes one.
"""

from backend.research.album import AlbumResearch
from backend.research.covers import CoverArt
from backend.research.http import SharedHttp, Throttle
from backend.research.models import ReleaseDetail, ReleaseGroup, ReleaseGroupMatch
from backend.research.musicbrainz import MusicBrainz
from backend.research.reviews import Reviews
from backend.research.safety import SafeFetcher
from backend.research.wikipedia import Wikipedia

__all__ = [
    "AlbumResearch",
    "CoverArt",
    "MusicBrainz",
    "ReleaseDetail",
    "ReleaseGroup",
    "ReleaseGroupMatch",
    "Reviews",
    "SafeFetcher",
    "SharedHttp",
    "Throttle",
    "Wikipedia",
]
