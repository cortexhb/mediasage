"""Every prompt the recommendation pipeline sends, in one place.

System prompts are constants; the user half is built by the functions below.
Each prompt states the JSON shape it wants back, and the module that calls it
parses exactly that shape -- changing one means changing the other.

Kept together so the sommelier's voice stays consistent across the four calls
a single recommendation makes.

Module-level functions on purpose: prompt text stays in one file rather than
following the stages that send it.
"""

from collections.abc import Sequence
from typing import Final

from backend.recommender.models import (
    AlbumRecommendation,
    AlbumRef,
    AnswerSet,
    ExtractedFacts,
    FamiliarityPreference,
    PitchValidation,
    SommelierPitch,
    TasteProfile,
)

# ── Familiarity ────────────────────────────────────────────────────────────
# Appended to the selection and pitch prompts. The braced levels match the
# markers `select_albums` puts on each album line.

SELECTION_FAMILIARITY: Final[dict[str, str]] = {
    "comfort": (
        "\n\nFAMILIARITY PREFERENCE: The user wants comfort picks. "
        "Strongly prefer albums marked {well-loved}. Avoid {unplayed} albums."
    ),
    "rediscover": (
        "\n\nFAMILIARITY PREFERENCE: The user wants to rediscover forgotten albums. "
        "Strongly prefer albums marked {light}, especially those not played recently. "
        "Avoid {unplayed} albums."
    ),
    "hidden_gems": (
        "\n\nFAMILIARITY PREFERENCE: The user wants hidden gems they haven't explored. "
        "Strongly prefer albums marked {unplayed}. Avoid {well-loved} albums."
    ),
}

PITCH_FAMILIARITY: Final[dict[str, str]] = {
    "comfort": (
        "\n\nFamiliarity framing: The user wants comfort picks — albums they already love. "
        "Frame pitches as celebrating a favorite: remind them why they love it, "
        "suggest a fresh angle to appreciate it anew.\n"
    ),
    "rediscover": (
        "\n\nFamiliarity framing: The user wants to rediscover forgotten albums. "
        "Frame pitches as 'when's the last time you sat down with this?' — "
        "highlight what they'll notice on a return visit.\n"
    ),
    "hidden_gems": (
        "\n\nFamiliarity framing: The user wants hidden gems they haven't explored. "
        "Frame pitches as exciting discovery: 'you haven't given this a real shot yet' — "
        "emphasize what makes it worth a dedicated listen.\n"
    ),
}

# ── Gap analysis ───────────────────────────────────────────────────────────

GAP_ANALYSIS_SYSTEM: Final = (
    "You are a music taste analyst. Given a user's album recommendation prompt, "
    "identify which 2 musical dimensions from the provided list would most help "
    "narrow down the perfect album. Return ONLY a JSON array of exactly 2 dimension "
    'IDs, e.g. ["energy", "emotional_direction"]. No explanation.'
)


def gap_analysis(prompt: str, catalogue: str) -> str:
    return (
        f'User wants: "{prompt}"\n\n'
        f"Available dimensions:\n{catalogue}\n\n"
        f"Which 2 dimensions have the biggest gap — where knowing the user's preference "
        f"would most change which album you'd recommend? Return JSON array of 2 IDs."
    )


# ── Filter suggestion ──────────────────────────────────────────────────────

FILTER_SYSTEM: Final = (
    "You are a music librarian helping pre-select filters for an album recommendation.\n"
    "Given a user's prompt, select which genres and decades from the available lists are RELEVANT.\n"
    "Rules:\n"
    "- Be inclusive but not indiscriminate.\n"
    "- For vague/mood prompts: select broadly but exclude clearly irrelevant genres "
    '(e.g., exclude Holiday for "dark and heavy").\n'
    "- For specific genre/era prompts: select narrowly.\n"
    "- When in doubt, include rather than exclude.\n"
    "- If no time period mentioned: select ALL decades.\n"
    'Return JSON: { "genres": [...], "decades": [...], "reasoning": "..." }'
)


def filters(prompt: str, genres: list[str], decades: list[str]) -> str:
    return (
        f'User wants: "{prompt}"\n\n'
        f"Available genres: {', '.join(genres)}\n\n"
        f"Available decades: {', '.join(decades)}\n\n"
        f"Which genres and decades are relevant?"
    )


# ── Question generation ────────────────────────────────────────────────────

QUESTIONS_SYSTEM: Final = (
    "You are a friendly music recommendation assistant. Generate exactly 2 clarifying "
    "questions to help pick the perfect album. Each question should:\n"
    "- Reference the user's words naturally\n"
    "- Have 3-4 short, tappable answer options\n"
    "- Address the specified musical dimension\n\n"
    "Return JSON array of objects with: question_text, options (array of 3-4 strings), "
    "dimension (the dimension id).\n"
    "No explanation, just the JSON array."
)


def questions(prompt: str, dimension_lines: list[str]) -> str:
    return (
        f'User wants: "{prompt}"\n\n'
        f"Dimensions to ask about:\n"
        + "\n".join(dimension_lines)
        + "\n\nGenerate 2 natural, conversational questions."
    )


# ── Library selection ──────────────────────────────────────────────────────

SMALL_POOL_NOTE: Final = (
    "\nNote: The pool is small. Pick the best matches available, "
    "even if the fit isn't perfect. Do your best with what's here."
)


def selection_system(familiarity_pref: FamiliarityPreference, picks: int) -> str:
    return (
        f"You are a music recommendation expert. Pick exactly {picks} albums from the "
        "provided list that best match the user's request and clarifying answers. The first "
        "pick is the PRIMARY recommendation (best match), the other two are SECONDARY "
        "(worth exploring).\n\n"
        f"Return a JSON array of {picks} objects, each with: artist (string), album (string), "
        'rank ("primary" for first, "secondary" for others). Pick from the list EXACTLY as '
        "written.\nNo explanation, just the JSON array."
        f"{SELECTION_FAMILIARITY.get(familiarity_pref, '')}"
    )


def selection(
    prompt: str, answers: AnswerSet, albums: str, count: int, picks: int, note: str
) -> str:
    return (
        f'User wants: "{prompt}"\n\n'
        f"Clarifying answers:\n{answers.for_selection()}\n\n"
        f"Available albums ({count} total):\n{albums}\n\n"
        f"Pick {picks} albums: 1 primary + {picks - 1} secondary.{note}"
    )


# ── Discovery selection ────────────────────────────────────────────────────


def discovery_system(picks: int) -> str:
    return (
        "You are a music recommendation expert with encyclopedic knowledge. "
        f"Recommend {picks} albums the user does NOT already own that match their request "
        "and taste profile. The first pick is the PRIMARY recommendation (best match), the "
        "others are SECONDARY.\n\n"
        "IMPORTANT: Do NOT recommend any album from the exclusion list below. "
        "Recommend real, existing albums with correct artist names and years.\n\n"
        f"Return a JSON array of {picks} objects, each with: artist (string), album (string), "
        'year (integer), rank ("primary" for first, "secondary" for others).\n'
        "No explanation, just the JSON array."
    )


def discovery(
    prompt: str,
    answers: AnswerSet,
    profile: TasteProfile,
    owned: Sequence[AlbumRef],
    already_shown: Sequence[AlbumRef],
    picks: int,
) -> str:
    shown = ""
    if already_shown:
        shown = "\n\nAlready recommended (DO NOT repeat these):\n" + "\n".join(
            f"- {ref}" for ref in already_shown
        )
    return (
        f'User wants: "{prompt}"\n\n'
        f"Clarifying answers:\n{answers.for_selection()}\n\n"
        f"User's taste profile:\n{profile.summary()}\n\n"
        f"Albums user already owns (DO NOT recommend these):\n"
        + "\n".join(f"- {ref}" for ref in owned)
        + f"{shown}\n\n"
        f"Recommend {picks} albums they don't own: 1 primary + {picks - 1} secondary."
    )


# ── Fact extraction ────────────────────────────────────────────────────────

FACTS_SYSTEM: Final = (
    "You are a music research assistant. Extract verifiable facts about a specific "
    "album from the provided sources. Follow these rules strictly:\n\n"
    "1. ONLY state facts that appear in the sources below. Do not add knowledge from "
    "your training data.\n"
    '2. If a topic is not covered in the sources, write "NOT IN SOURCES" for that field.\n'
    "3. If sources conflict on a point, note the conflict.\n"
    "4. Be specific to THIS album — do not generalize from the artist's broader catalog.\n"
    "5. For vocal_approach, note the specific language(s) used and whether it varies by track.\n"
    "6. For common_misconceptions, note anything the sources clarify that could easily be "
    "misunderstood or overgeneralized.\n\n"
    "Return a JSON object with these fields:\n"
    "- origin_story: How/why the album was made, key events in its creation\n"
    "- personnel: List of key people involved (musicians, producers, engineers)\n"
    "- musical_style: Sound, instrumentation, production approach\n"
    "- vocal_approach: Language(s) sung in, singing style, notable vocal choices\n"
    "- cultural_context: Reception, significance, scene/movement\n"
    "- track_highlights: Notable individual tracks mentioned in sources\n"
    "- common_misconceptions: Things sources clarify or correct about common assumptions\n"
    "- source_coverage: Brief note on what topics the sources cover well vs poorly\n\n"
    "No explanation, just the JSON object."
)


def facts(ref: AlbumRef, sources: str) -> str:
    return f"Album: {ref}\n\nSOURCES:\n{sources}\n\nExtract the structured facts."


# ── Pitch writing ──────────────────────────────────────────────────────────

GROUNDING_RULES: Final = (
    "\n\nGROUNDING RULES (mandatory when EXTRACTED FACTS are provided):\n"
    "- Base all factual claims on the EXTRACTED FACTS provided for each album. "
    "Do not rely on general knowledge about the artist when it conflicts with "
    "album-specific facts.\n"
    '- If a fact is marked "NOT IN SOURCES," do not make claims about that topic. '
    "Write around it or keep the language vague and subjective.\n"
    "- Never generalize from an artist's broader catalog to this specific album. "
    "What is true of an artist in general may not be true of this particular record.\n"
    "- Distinguish between the album's actual story and a plausible-sounding narrative. "
    "If the origin field describes specific events, use those — do not invent "
    "a more dramatic or simplified version.\n"
    "- Pay close attention to the 'Common misconceptions' field — these are facts "
    "that are easily gotten wrong.\n"
)


def pitch_system(grounded: bool, familiarity_pref: FamiliarityPreference) -> str:
    return (
        "You are a passionate music sommelier. Write compelling pitches for album "
        "recommendations.\n\n"
        "For the PRIMARY album, write:\n"
        "- hook: A compelling one-liner that makes someone want to press play immediately\n"
        "- context: An interesting detail about the album (recording story, cultural "
        "significance, artist journey)\n"
        "- listening_guide: How to approach the listen — what to expect as it unfolds\n"
        "- connection: Why THIS album matches THIS specific request\n\n"
        "For each SECONDARY album, write:\n"
        "- short_pitch: 2-3 vivid sentences that sell the album\n\n"
        "Use specific, vivid language. Reference the user's words. Avoid generic "
        "music-critic clichés.\n"
        f"{GROUNDING_RULES if grounded else ''}"
        f"{PITCH_FAMILIARITY.get(familiarity_pref, '')}\n"
        "Return JSON array of objects with: artist, album, hook, context, listening_guide, "
        "connection (for primary), or short_pitch (for secondary). Include all applicable "
        "fields.\nNo explanation, just the JSON array."
    )


def pitches(prompt: str, answers: AnswerSet, albums: str) -> str:
    return (
        f'User wanted: "{prompt}"\n'
        f"Their preferences: {answers.for_pitch()}\n\n"
        f"Albums to pitch:\n{albums}\n\n"
        f"Write the pitches."
    )


# ── Pitch validation ───────────────────────────────────────────────────────

VALIDATION_SYSTEM: Final = (
    "You are a fact-checker reviewing an album recommendation pitch against "
    "research data. Flag claims that:\n"
    "1. Contradict the extracted facts\n"
    "2. Are not supported by any source and could be wrong (specific biographical "
    "events, specific recording details, specific personnel claims)\n"
    "3. Overgeneralize from the artist's catalog to this specific album\n"
    "4. Mischaracterize events (e.g., 'toured with' vs 'rehearsed with')\n"
    "5. Reference specific track names that do NOT appear in the AUTHORITATIVE TRACK "
    "LISTING. If the pitch mentions a track by name, it must match a track in the "
    "listing (minor punctuation differences are OK).\n\n"
    "Do NOT flag:\n"
    "- Subjective/editorial language (e.g., 'sonic warm bath', 'ethereal')\n"
    "- Vague statements that don't make specific factual claims\n"
    "- Opinions about how the album sounds or feels\n\n"
    'Return a JSON object: {"valid": true} if no issues, or '
    '{"valid": false, "issues": [{"claim": "...", "problem": "...", '
    '"correction": "..."}]} if issues found.\n'
    "No explanation, just the JSON object."
)


def validation(pitch: SommelierPitch, facts_text: str) -> str:
    return (
        f"PITCH TO CHECK:\n{pitch.full_text}\n\n"
        f"EXTRACTED FACTS:\n{facts_text}\n\n"
        f"Are there any factual inaccuracies in the pitch?"
    )


# ── Pitch rewriting ────────────────────────────────────────────────────────

REWRITE_SYSTEM: Final = (
    "You are a passionate music sommelier. Rewrite this album pitch, fixing the "
    "factual errors listed below. Keep the same tone, structure, and enthusiasm — "
    "only change the parts that are factually wrong.\n\n"
    "Write:\n"
    "- hook: A compelling one-liner\n"
    "- context: An interesting factual detail about the album\n"
    "- listening_guide: How to approach the listen\n"
    "- connection: Why this album matches the request\n\n"
    "Return a JSON object with: hook, context, listening_guide, connection.\n"
    "No explanation, just the JSON object."
)


def rewrite(
    rec: AlbumRecommendation,
    prompt: str,
    answers: AnswerSet,
    issues: PitchValidation,
    facts: ExtractedFacts,
) -> str:
    return (
        f"Album: {rec.ref} ({rec.year or '?'})\n"
        f'User wanted: "{prompt}"\n'
        f"Their preferences: {answers.for_pitch()}\n\n"
        f"CORRECTIONS (do not repeat these errors):\n{issues.corrections()}\n\n"
        f"EXTRACTED FACTS:\n{facts.to_text()}\n\n"
        f"ORIGINAL PITCH:\n{rec.pitch.full_text}\n\n"
        f"Rewrite the pitch fixing the errors above."
    )


# ── Discovery validation ───────────────────────────────────────────────────

DISCOVERY_VALIDATION_SYSTEM: Final = (
    "You are validating an album recommendation. Given the user's request and "
    "research data about the album, determine if this album genuinely matches "
    "the request in terms of genre, mood, and character.\n\n"
    'Return ONLY a JSON object: {"valid": true} or {"valid": false, "reason": "..."}'
)


def discovery_validation(prompt: str, research_text: str) -> str:
    return (
        f'User wanted: "{prompt}"\n\n'
        f"Album research:\n{research_text}\n\n"
        f"Does this album genuinely match the request?"
    )
