/**
 * What the settings rail offers, and which sections each entry writes.
 *
 * The grouping is the one thing the schema cannot supply: it is editorial —
 * `budget` belongs beside `library` because both are about how much of a
 * library one prompt carries, and nothing in `MediasageConfig` says so.
 * Section and field names still come from the schema.
 *
 * `bespoke` names the fields a hand-written organism already draws. Those are
 * skipped by the generated list rather than dropped from the form, because
 * Plex sign-in, Ollama probing and provider branching are not plain inputs.
 */

export interface SettingsGroup {
  /** The path under `/settings`, and the rail's key. */
  readonly slug: string
  readonly title: string
  readonly blurb: string
  /** Config sections this group writes, in the order they are drawn. */
  readonly sections: readonly string[]
  /** `section.field` names an organism on this page already renders. */
  readonly bespoke: readonly string[]
}

export const SETTINGS_GROUPS: readonly SettingsGroup[] = [
  {
    slug: 'plex',
    title: 'Plex',
    blurb: 'Which server holds your music, and how hard to lean on it.',
    sections: ['plex'],
    bespoke: ['plex.music_library'],
  },
  {
    slug: 'ai',
    title: 'AI Provider',
    blurb: 'Who serves the model, which models, and what a call costs.',
    sections: ['llm'],
    bespoke: [
      'llm.provider',
      'llm.api_key',
      'llm.model_analysis',
      'llm.model_generation',
      'llm.smart_generation',
      'llm.context_window',
      'llm.endpoint_url',
    ],
  },
  {
    slug: 'library',
    title: 'Library',
    blurb:
      'How the local mirror is synced, and how much of it one prompt carries.',
    sections: ['library', 'budget'],
    bespoke: [],
  },
  {
    slug: 'recommend',
    title: 'Recommendations',
    blurb:
      'The shape of a round, how names are matched, and what is researched.',
    sections: ['recommend', 'matching', 'research', 'defaults'],
    bespoke: [],
  },
  {
    slug: 'advanced',
    title: 'Advanced',
    blurb:
      'Album art and tracing. The defaults here were measured, not guessed.',
    sections: ['art', 'langfuse'],
    bespoke: [],
  },
]

/** The group a slug names, or nothing where the path is not one of ours. */
export function groupBySlug(
  slug: string | undefined,
): SettingsGroup | undefined {
  return SETTINGS_GROUPS.find((group) => group.slug === slug)
}
