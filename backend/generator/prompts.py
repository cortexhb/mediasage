"""Every prompt playlist generation sends, in one place.

System prompts are constants; the user half is built by the functions below.
Each states the JSON shape it wants back, and `playlists.py` parses exactly
that shape -- changing one means changing the other.

Module-level functions on purpose: prompt text stays in one file rather than
following the models that send it.
"""

from collections.abc import Sequence
from typing import Final

from backend.models import Track

# Tracks quoted back when asking for a title and narrative. The whole playlist
# is context spent on a three-sentence answer that names four songs.
NARRATIVE_TRACK_LIMIT: Final = 15

GENERATION_SYSTEM = """You are a music curator creating a playlist from a user's music library.

You will be given:
1. A description of what the user wants (prompt, seed track dimensions, or both)
2. A numbered list of tracks that are available in their library

Your task is to select tracks that best match the user's request. For each track, include a brief reason (1 sentence) explaining why it fits.

Guidelines:
- Select tracks that fit the mood, era, style, and other aspects of the request
- Vary the selection - don't pick too many tracks from the same artist or album
- Consider the flow of the playlist - how tracks will sound in sequence
- If using a seed track, don't include the seed track itself in the results

Return ONLY a JSON array like:
[
  {"artist": "Artist Name", "album": "Album Name", "title": "Track Title", "reason": "Brief explanation of why this track fits."},
  ...
]

No markdown formatting, no explanations - just the JSON array."""


NARRATIVE_SYSTEM = """You are a music connoisseur writing a brief liner note for a playlist.

Given the user's original request and the track selections (with reasons), create:
1. A creative playlist title (2-5 words, evocative, do NOT include any date)
2. A brief narrative (3 sentences, under 400 characters) that:
   - Reflects the mood or theme the user asked for
   - Mentions 3-4 specific songs by name (use single quotes around song names, e.g. 'Skinny Love')

Sound like a passionate music lover. Be concise.

Return ONLY valid JSON:
{"title": "Creative Title Here", "narrative": "Your brief narrative with 'song names' in single quotes..."}

No markdown formatting, no explanations - just the JSON object."""


def selection(
    tracks: list[Track],
    track_count: int,
    prompt: str = "",
    seed_track: Track | None = None,
    selected_dimensions: Sequence[str] = (),
    additional_notes: str = "",
    refinement_answers: Sequence[str | None] = (),
) -> str:
    """What the user asked for, then every track they own that could answer it.

    The library goes last: it is the long part, and a model reads the request
    before it reads the catalogue.

    Args:
        tracks: Every track the filters left in play, numbered for the model
        track_count: How many to pick
        prompt: The user's request, when they typed one
        seed_track: The track to explore from, when they picked one
        selected_dimensions: Which of the seed's dimensions to follow
        additional_notes: Free text the user added
        refinement_answers: Their answers to the refinement questions; blanks
            are dropped rather than sent as empty preferences
    """
    parts = []

    if prompt:
        parts.append(f"User's request: {prompt}")

    if seed_track:
        parts.append(
            f"Seed track: {seed_track.title} by {seed_track.artist} "
            f"(from {seed_track.album}, {seed_track.year or 'Unknown year'})"
        )
        if selected_dimensions:
            parts.append(f"Explore these dimensions: {', '.join(selected_dimensions)}")

    if additional_notes:
        parts.append(f"Additional notes: {additional_notes}")

    if refinement_answers:
        answered = [answer for answer in refinement_answers if answer]
        if answered:
            parts.append(f"User preferences: {', '.join(answered)}")

    listing = "\n".join(
        f"{index + 1}. {track.artist} - {track.title} "
        f"({track.album}, {track.year or 'Unknown year'})"
        for index, track in enumerate(tracks)
    )
    parts.append(f"\nSelect {track_count} tracks from this library:\n{listing}")

    return "\n\n".join(parts)


def narrative(track_selections: list[dict], user_request: str = "") -> str:
    """The picked tracks and why each was picked, for the liner note."""
    chosen = "\n".join(
        f"- {selection.get('artist', 'Unknown')} - "
        f'"{selection.get("title", "Unknown")}": '
        f"{selection.get('reason', 'Selected for this playlist')}"
        for selection in track_selections[:NARRATIVE_TRACK_LIMIT]
    )

    if user_request:
        return f"User's request: {user_request}\n\nSelected tracks:\n{chosen}"
    return f"Selected tracks:\n{chosen}"
