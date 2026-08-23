"""Every prompt the analyzer sends, in one place.

System prompts are constants; the user half is built by the functions below.
Each states the JSON shape it wants back, and `analysis.py` parses exactly that
shape -- changing one means changing the other.

Module-level functions on purpose: prompt text stays in one file rather than
following the models that send it.
"""

from typing import Final

from backend.models import LibraryStatsResponse, Track

# Genres named in the prompt, most-played first. The whole tag list of a large
# library is tokens spent on names the model will not pick anyway.
GENRE_LIMIT: Final = 30

PROMPT_ANALYSIS_SYSTEM = """You are a music expert helping to create playlists from a user's music library.

Analyze the user's prompt and suggest appropriate filters (genres and decades) that would help find matching tracks.

Return a JSON object with:
- genres: Array of genre names that match the prompt (e.g., ["Alternative", "Rock", "Indie"])
- decades: Array of decade strings (e.g., ["1990s", "2000s"])
- reasoning: Brief explanation of why you chose these filters

Be specific about genres and decades. Consider:
- Mood/atmosphere (melancholy, upbeat, energetic)
- Era references (90s, classic, modern)
- Genre keywords (alternative, jazz, electronic)
- Artist style hints

Return ONLY valid JSON, no markdown formatting."""


TRACK_ANALYSIS_SYSTEM = """You are a music expert analyzing a song to identify its distinctive characteristics.

Given a track's title, artist, album, and year, identify 5-7 specific musical dimensions that make this track unique. These dimensions will help the user explore similar music.

For each dimension, provide:
- id: A short identifier (e.g., "mood", "era", "instrumentation")
- label: A specific, evocative label (NOT generic like "the mood" - be specific like "The melancholy, bittersweet mood")
- description: A brief explanation of this dimension

Make dimensions SPECIFIC to this track, not generic. Bad: "The genre". Good: "90s British alternative rock with Britpop influences".

Return a JSON object with:
{
  "dimensions": [
    {"id": "mood", "label": "The melancholy, introspective mood", "description": "..."},
    ...
  ]
}

Return ONLY valid JSON, no markdown formatting."""


def filters(prompt: str, stats: LibraryStatsResponse) -> str:
    """The request, and the filters the library has to offer for it."""
    genres = ", ".join(
        f"{g.name} ({g.count})" if g.count else g.name for g in stats.genres[:GENRE_LIMIT]
    )
    decades = ", ".join(f"{d.name} ({d.count})" if d.count else d.name for d in stats.decades)

    return f"""User's playlist request: "{prompt}"

Available genres in their library:
{genres}

Available decades in their library:
{decades}

Suggest genres and decades from the available options that best match the user's request."""


def track(seed: Track) -> str:
    """One track as the dimension analysis sees it."""
    return f"""Analyze this track:
Title: {seed.title}
Artist: {seed.artist}
Album: {seed.album}
Year: {seed.year or "Unknown"}
Genres: {", ".join(seed.genres) if seed.genres else "Unknown"}

Identify 5-7 specific musical dimensions that make this track distinctive."""
