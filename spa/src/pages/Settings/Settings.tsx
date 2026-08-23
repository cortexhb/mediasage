/**
 * Settings — the only place the app is configured.
 *
 * The legacy setup wizard is gone (see `spa/docs/migration.md`), so this
 * screen has to configure a system from nothing. It therefore shows three
 * things `/api/config` does not carry and only `/api/setup/status` knows: the
 * libraries a connected server offers, which values the deployment supplies
 * through the environment, and whether the data directory can be written.
 *
 * The loader fills it once; the save is a plain call and its answer is held
 * here. Deliberately not a route action — see `libs/saveSettings`.
 *
 * The fields below are uncontrolled, which is what makes adopting the saved
 * settings safe: the statuses refresh and nothing the user typed moves.
 */
import { useEffect, useRef, useState } from 'react'
import { useLoaderData } from 'react-router'

import { Button } from '../../components/atoms/Button/Button.tsx'
import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { StorageWarning } from '../../components/molecules/StorageWarning/StorageWarning.tsx'
import { PlexSettings } from '../../components/organisms/PlexSettings/PlexSettings.tsx'
import { ProviderSettings } from '../../components/organisms/ProviderSettings/ProviderSettings.tsx'
import type { SettingsData } from '../../libs/loadSettings/loadSettings.ts'
import type { SaveOutcome } from '../../libs/saveSettings/saveSettings.ts'
import { saveSettings } from '../../libs/saveSettings/saveSettings.ts'
import styles from './Settings.module.scss'

/** What a save is doing while it looks like nothing is happening. */
const CHECKING = 'Checking Plex and the provider, then saving…'

/** What the last save left behind, before one has been made. */
const NOTHING_KEPT: {
  readonly config: SettingsData['config'] | undefined
  readonly setup: SettingsData['setup'] | undefined
} = { config: undefined, setup: undefined }

export function Settings() {
  const loaded = useLoaderData<SettingsData>()
  const [kept, setKept] = useState(NOTHING_KEPT)
  const [outcome, setOutcome] = useState<SaveOutcome | undefined>()
  const [saving, setSaving] = useState(false)
  const form = useRef<HTMLFormElement>(null)
  const sending = useRef<AbortController>(null)

  const config = kept.config ?? loaded.config
  const setup = kept.setup ?? loaded.setup

  // Leaving mid-save drops the answer; the write itself already happened.
  useEffect(() => () => sending.current?.abort(), [])

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

    saveSettings(fields, sending.current.signal).then(
      (result) => {
        setSaving(false)
        setOutcome(result)
        if (!result.saved) return
        setKept({ config: result.config, setup: result.setup })
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
      className={styles.settings}
      // Named, so it is a landmark rather than an anonymous group.
      aria-label="Settings"
      aria-busy={saving}
      data-saving={saving ? '' : undefined}
    >
      <Heading level={2}>Settings</Heading>

      <PlexSettings
        library={config.music_library}
        connected={config.plex_connected}
        linked={config.plex_linked}
        serverName={config.plex_server_name}
        serverId={config.plex_server_id}
        libraries={setup.music_libraries ?? []}
      />

      <ProviderSettings config={config} />

      <StorageWarning
        writable={setup.data_dir_writable}
        directory={setup.data_dir}
        uid={setup.process_uid}
        gid={setup.process_gid}
      />

      <div className={styles.settings__save}>
        <Button variant="primary" type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save Settings'}
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
