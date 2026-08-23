"""Playlist generation: a sentence and a library, into a Plex playlist.

  models     TrackPool, TrackMatcher and Narrative, the shapes a run passes
  prompts    every word sent to a model, and nothing else
  playlists  PlaylistGeneration, one run from request to saved result

`PlaylistGeneration.stream` is the entry point; it yields SSE frames so the
page can show progress while a large library is filtered and matched.
"""

from backend.generator import prompts
from backend.generator.models import Narrative, TrackMatcher, TrackPool
from backend.generator.playlists import PlaylistGeneration

__all__ = [
    "Narrative",
    "PlaylistGeneration",
    "TrackMatcher",
    "TrackPool",
    "prompts",
]
