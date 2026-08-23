/**
 * The Plex half of Settings: where the server is, how to reach it, and which
 * library holds the music.
 *
 * A value the deployment supplies through the environment is shown and
 * disabled rather than hidden, so what is in force is visible without
 * reading `.env`.
 */
import { Status } from '../../atoms/Status/Status.tsx'
import { Field } from '../../molecules/Field/Field.tsx'
import { LibraryField } from '../../molecules/LibraryField/LibraryField.tsx'
import { Section } from '../../molecules/Section/Section.tsx'
import { LibraryStats } from '../LibraryStats/LibraryStats.tsx'

/** Shown where a credential is already stored, in place of its value. */
const STORED = '••••••••••••••••  (configured)'

export interface PlexSettingsProps {
  readonly url: string
  readonly library: string
  readonly connected: boolean
  readonly tokenSet: boolean
  readonly fromEnv: boolean
  readonly libraries: readonly string[]
}

export function PlexSettings({
  url,
  library,
  connected,
  tokenSet,
  fromEnv,
  libraries,
}: PlexSettingsProps) {
  return (
    <Section title="Plex Connection">
      <Status state={connected ? 'connected' : 'unknown'}>
        {connected ? 'Connected' : 'Not connected'}
      </Status>

      <Field
        label="Plex Server URL"
        name="plex_url"
        type="url"
        defaultValue={url}
        placeholder="http://your-plex-server:32400"
        disabled={fromEnv}
        {...(fromEnv && {
          hint: 'Set by the environment. Edit .env to change.',
        })}
      />
      <Field
        label="Plex Token"
        name="plex_token"
        type="password"
        autoComplete="off"
        placeholder={tokenSet ? STORED : 'Your Plex token'}
        disabled={fromEnv}
        hint="Leave blank to keep the stored token."
      />
      <LibraryField value={library} libraries={libraries} />
      <LibraryStats connected={connected} />
    </Section>
  )
}
