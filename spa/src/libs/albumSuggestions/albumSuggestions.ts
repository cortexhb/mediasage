/**
 * The suggestions under the album prompt box, copied from `frontend/app.js:3831`.
 *
 * A separate set from the playlist flow's: these ask for one record, so they
 * name artists to sound like and albums to be pointed at rather than moods to
 * fill an hour with. Picking from them is `libs/promptSuggestions`.
 *
 * Prompt text lives in one file, per `CLAUDE.md`: these are words a model
 * eventually reads.
 */
import type { SuggestionGroups } from '../promptSuggestions/pickSuggestions.ts'

/** Six groups: mood, sounds-like, genre, era, occasion, deep cuts. */
export const ALBUM_PROMPT_GROUPS: SuggestionGroups = [
  /* Mood / Vibe */
  [
    'Melancholy I want to sit inside',
    'Warm and analog, like vinyl sounds',
    'Bleak and beautiful at once',
    'Joyful with no irony in it',
    "Unsettling in a way I can't name",
    'Tender without being soft',
    'Cold and a little industrial',
    'Romantic but not embarrassing',
    'Restless and searching',
    'Nostalgic for a time before me',
    'Built for a real release',
    'Dense and patient, rewards time',
    'Strange and slightly off-kilter',
    'Cinematic, feels like a place',
    'Austere, almost nothing there',
    "Deeply sad, don't soften it",
    'Euphoric and earned, not cheap',
  ],
  /* Sounds-Like */
  [
    'Radiohead, but room to breathe',
    'Nick Cave with some hope left',
    'Early Springsteen, less polish',
    'Joni Mitchell making a jazz record',
    'Prince stripped to the bones',
    'Arcade Fire, quieter ambition',
    'Kendrick but more internal',
    'Tom Waits went fully ambient',
    "D'Angelo but tighter",
    'Velvet Underground energy',
    'PJ Harvey, more acoustic',
    'Late Miles Davis, electric',
    'Talking Heads but darker',
    'Coltrane went electric',
    'Portishead but less cold',
    'Neil Young without the dust',
    'Massive Attack but warmer',
  ],
  /* Genre Exploration */
  [
    'First jazz album, where to start',
    'Introduce me to krautrock',
    'Best entry point for ambient',
    'Soul that invented the form',
    'Metal without prior loyalty needed',
    'Country with actual grit in it',
    'Electronic that feels something',
    "Folk that doesn't lose me",
    'Hip hop with real patience in it',
    'Reggae beyond the obvious three',
    'Post-punk, angular, still alive',
    'Classical with a clear narrative',
    'Afrobeat with real propulsion',
    'Gospel with conviction, not comfort',
    'Experimental but I can stay',
    'Brazilian music beyond bossa',
    'Blues that explains what came after',
  ],
  /* Era / Era-Adjacent */
  [
    'Timeless, no decade owns it',
    'Pure 1970s warmth, room sound',
    'Sounds like 1983, best way',
    'Late 60s psychedelia, still intact',
    'Early 90s indie, lo-fi earnest',
    '1970s jazz fusion at its peak',
    'Mid-90s hip hop, NY and hungry',
    '80s synth that aged well',
    'Late 90s slowcore, unsparing',
    '2001–2005 indie rock landmark',
    '1960s soul, Detroit or Memphis',
    '70s singer-songwriter, confessional',
    '80s post-punk, cold and correct',
    '90s electronic, pre-mainstream',
    'Early 2000s R&B, sophisticated',
    'Recorded in the 70s, sounds eternal',
    '1960s modal jazz, serious',
  ],
  /* Emotional Occasion */
  [
    'Breakup, raw and recent',
    'Something ended well',
    'First listen back after time away',
    'Celebrating quietly, just yourself',
    'Heavy with no explanation',
    'The week before everything changes',
    'Feeling invisible, fine with it',
    'Early stage of falling for someone',
    'Grieving, need company in it',
    'Long Sunday, nowhere to be',
    'Proud and exhausted equally',
    '3am, completely awake',
    'The last day of something',
    'Ready to start over, actually ready',
    'Complicated happy',
    'Homesick for somewhere unreachable',
    'Tired of holding it together',
  ],
  /* Deep Cuts / Underrated */
  [
    'A masterpiece nobody talks about',
    'Criminally overlooked',
    'Best album, not their famous one',
    'Too weird for radio, too good',
    'One great record, then gone',
    'Cult classic, devoted few',
    'Critics loved it, world moved on',
    'Ahead of its time',
    'The album that got away',
    'Debut that deserved a career',
    'Side project better than the main',
    'Reissued, finally getting its due',
    'Sounds like nothing else here',
    'Famous producer, album outshines',
    'The one even fans missed',
  ],
]
