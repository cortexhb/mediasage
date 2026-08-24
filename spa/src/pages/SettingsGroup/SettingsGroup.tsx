/**
 * One group of settings, and the save that writes only that group.
 *
 * Every group is this component: which sections it draws comes from
 * `libs/settingsGroups`, and which fields those sections have comes from the
 * API's schema. Plex and the AI provider additionally render a hand-written
 * organism first, because a sign-in, an Ollama probe and provider branching
 * are not plain inputs; the fields those organisms already draw are named in
 * the group's `bespoke` list and skipped by the generated ones.
 *
 * The save is a plain call, not a route action — see `libs/saveSettings`. Its
 * answer replaces the config held here, so the statuses refresh and nothing
 * the user typed moves.
 */
import { useEffect, useRef, useState } from 'react'
import { useOutletContext, useParams } from 'react-router'

import { Button } from '../../components/atoms/Button/Button.tsx'
import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { Section } from '../../components/molecules/Section/Section.tsx'
import { SchemaField } from '../../components/molecules/SchemaField/SchemaField.tsx'
import { PlexSettings } from '../../components/organisms/PlexSettings/PlexSettings.tsx'
import { ProviderSettings } from '../../components/organisms/ProviderSettings/ProviderSettings.tsx'
import { PatchFields } from '../../libs/patchFields/patchFields.ts'
import type { SettingsData } from '../../libs/loadSettings/loadSettings.ts'
import type { SaveOutcome } from '../../libs/saveSettings/saveSettings.ts'
import { saveSettings } from '../../libs/saveSettings/saveSettings.ts'
import { groupBySlug } from '../../libs/settingsGroups/settingsGroups.ts'
import { NotFound } from '../NotFound/NotFound.tsx'
import styles from './SettingsGroup.module.scss'

/** What a save is doing while it looks like nothing is happening. */
const CHECKING = 'Checking what the change touches, then saving…'

/** How a section name reads as a heading, where the schema gives no title. */
const TITLES: Record<string, string> = {
  plex: 'Plex Server',
  llm: 'LLM Provider',
  library: 'Library Sync',
  budget: 'Prompt Budget',
  recommend: 'Recommendation Rounds',
  matching: 'Fuzzy Matching',
  research: 'Research Sources',
  defaults: 'Defaults',
  art: 'Album Art',
  langfuse: 'Tracing',
}

export function SettingsGroup() {
  const loaded = useOutletContext<SettingsData>()
  const { group: slug } = useParams()
  const group = groupBySlug(slug)

  const [kept, setKept] = useState<SettingsData['config'] | undefined>()
  // Re-read after a save: a Plex sign-in moves the library list.
  const [status, setStatus] = useState<SettingsData['setup'] | undefined>()
  const [outcome, setOutcome] = useState<SaveOutcome | undefined>()
  const [saving, setSaving] = useState(false)
  const form = useRef<HTMLFormElement>(null)
  const sending = useRef<AbortController>(null)

  // Leaving mid-save drops the answer; the write itself already happened.
  useEffect(() => () => sending.current?.abort(), [])

  if (group === undefined) return <NotFound />

  const config = kept ?? loaded.config
  const setup = status ?? loaded.setup
  const skipped = new Set(group.bespoke)

  /** Wipe the credential fields, so a later save cannot resend one. */
  const forget = (): void => {
    for (const field of form.current?.querySelectorAll(
      'input[type=password]',
    ) ?? []) {
      ;(field as HTMLInputElement).value = ''
    }
  }

  const submit = (
    event: React.SyntheticEvent<HTMLFormElement, SubmitEvent>,
  ): void => {
    event.preventDefault()
    if (saving) return

    const fields = new FormData(event.currentTarget)
    sending.current = new AbortController()
    setSaving(true)
    setOutcome(undefined)

    saveSettings(
      fields,
      PatchFields.kinds(loaded.fields),
      sending.current.signal,
    ).then(
      (result) => {
        setSaving(false)
        setOutcome(result)
        if (!result.saved) return
        setKept(result.config)
        // Undefined when the re-read failed, and the held one still stands.
        if (result.setup) setStatus(result.setup)
        forget()
      },
      // Unreachable: a failure comes back as an outcome, not as a throw.
      () => {
        setSaving(false)
      },
    )
  }

  return (
    <form
      onSubmit={submit}
      ref={form}
      className={styles.settingsGroup}
      aria-label={group.title}
      aria-busy={saving}
      data-saving={saving ? '' : undefined}
      // Remounted per group, so a switch never carries the last one's values.
      key={group.slug}
    >
      <header className={styles.settingsGroup__header}>
        <Heading level={3}>{group.title}</Heading>
        <Text tone="muted">{group.blurb}</Text>
      </header>

      {group.slug === 'plex' && (
        <PlexSettings
          library={config.sections.plex?.music_library ?? ''}
          connected={config.plex_connected}
          linked={config.plex_linked}
          serverName={config.sections.plex?.server_name ?? ''}
          serverId={config.sections.plex?.server_id ?? ''}
          libraries={setup.music_libraries ?? []}
        />
      )}

      {group.slug === 'ai' && <ProviderSettings config={config} />}

      {group.sections.map((section) => {
        const fields = loaded.fields.filter(
          (field) => field.section === section && !skipped.has(field.name),
        )
        if (fields.length === 0) return null
        const held = config.sections[
          section as keyof typeof config.sections
        ] as Record<string, unknown> | undefined

        return (
          <Section key={section} title={TITLES[section] ?? section}>
            {fields.map((field) => (
              <SchemaField
                key={field.name}
                field={field}
                value={held?.[field.field]}
              />
            ))}
          </Section>
        )
      })}

      <div className={styles.settingsGroup__save}>
        <Button variant="primary" type="submit" disabled={saving}>
          {saving ? 'Saving…' : `Save ${group.title}`}
        </Button>

        {saving ? (
          // The button sits below the fold, so it alone says nothing.
          <Text tone="muted" role="status">
            {CHECKING}
          </Text>
        ) : (
          outcome && (
            <Text
              tone={outcome.saved ? 'success' : 'error'}
              role={outcome.saved ? 'status' : 'alert'}
            >
              {outcome.message}
            </Text>
          )
        )}
      </div>
    </form>
  )
}
