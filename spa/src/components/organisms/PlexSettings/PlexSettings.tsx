/**
 * The Plex half of Settings: who is signed in, which server, which library.
 *
 * There is no URL field and no token field. Signing in is the only way the
 * app reaches a server, so this card walks the pin exchange — see
 * `docs/plex_login.md` and `libs/usePlexLink`.
 *
 * The server is a select rather than something behind a button: which one is
 * in force is a setting, and a setting is shown where it can be changed.
 *
 * `music_library` is the one Plex value the settings form still submits;
 * everything else here writes through `/api/plex/*` as it is done.
 *
 * The sync button reads the shell's poller rather than its own, so starting a
 * sync here is the same sync the status bar reports.
 */
import { useSharedLibrarySync } from '../../../libs/useLibrarySync/useLibrarySync.ts'
import { usePlexLink } from '../../../libs/usePlexLink/usePlexLink.ts'
import { Button } from '../../atoms/Button/Button.tsx'
import { Status } from '../../atoms/Status/Status.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import { LibraryField } from '../../molecules/LibraryField/LibraryField.tsx'
import { Section } from '../../molecules/Section/Section.tsx'
import { SelectField } from '../../molecules/SelectField/SelectField.tsx'
import { LibraryStats } from '../LibraryStats/LibraryStats.tsx'
import styles from './PlexSettings.module.scss'

const SIGNED_OUT = 'Sign in to Plex so MediaSage can read your library.'
const APPROVE = 'Approve this code in the Plex tab, then come back here.'
const BLOCKED = 'No tab opened? Approve the sign-in here.'
const NO_SERVERS = 'This Plex account has no servers on it.'
const UNCHOSEN = 'Signed in to Plex. Choose which server holds your music.'
const WORKING = 'Talking to Plex…'
const SWITCHES = 'Changing this reconnects and reloads the library list.'

export interface PlexSettingsProps {
  readonly library: string
  readonly connected: boolean
  readonly linked: boolean
  readonly serverName: string
  readonly serverId: string
  readonly libraries: readonly string[]
}

export function PlexSettings({
  library,
  connected,
  linked,
  serverName,
  serverId,
  libraries,
}: PlexSettingsProps) {
  const plex = usePlexLink(linked)
  const sync = useSharedLibrarySync()
  const syncing = sync.status?.is_syncing ?? false

  // A sign-in outranks the loader, which has not reread the config.
  const now = plex.linked ?? {
    linked,
    connected,
    server_name: serverName,
    server_id: serverId,
    music_libraries: libraries,
  }
  const offered = now.music_libraries ?? []
  const chosen = now.server_name ?? ''
  // Sticky: a sign-in this session outlives a config that predates it.
  const signedIn = now.linked || plex.signedIn

  const options = plex.servers.map((server) => ({
    value: server.id,
    label: server.owned ? server.name : `${server.name} (shared)`,
  }))

  /**
   * Open the tab in the click itself.
   *
   * A popup opened after the pin request returns is blocked, so the tab is
   * opened empty and pointed at plex.tv once the address is known.
   */
  const start = (): void => {
    plex.signIn(window.open('', '_blank'))
  }

  const servers = (hint: string) => (
    <SelectField
      label="Plex Server"
      value={now.server_id ?? ''}
      onChange={(event) => {
        plex.choose(event.target.value)
      }}
      options={options}
      placeholder="-- Select server --"
      hint={hint}
    />
  )

  return (
    <Section title="Plex Connection">
      <div className={styles.plex}>
        {plex.stage === 'busy' ? (
          // Its own branch: the config still says signed out mid-sign-in.
          <Status state="unknown">{WORKING}</Status>
        ) : plex.stage === 'waiting' ? (
          <>
            <Text>{APPROVE}</Text>
            <p className={styles.plex__code}>{plex.code}</p>
            <a
              className={styles.plex__approve}
              href={plex.approvalUrl}
              target="_blank"
              rel="noreferrer"
            >
              {BLOCKED}
            </a>
            <div className={styles.plex__actions}>
              <Button variant="secondary" onClick={plex.cancel}>
                Cancel
              </Button>
            </div>
          </>
        ) : plex.stage === 'choosing' ? (
          <>
            <Text>{UNCHOSEN}</Text>
            {options.length === 0 ? (
              <Text tone="muted">{NO_SERVERS}</Text>
            ) : (
              servers(SWITCHES)
            )}
            <div className={styles.plex__actions}>
              <Button variant="ghost" onClick={plex.signOut}>
                Sign out
              </Button>
            </div>
          </>
        ) : !signedIn ? (
          <>
            <Status state="unknown">Not signed in</Status>
            <Text tone="muted">{SIGNED_OUT}</Text>
            <div className={styles.plex__actions}>
              <Button variant="primary" onClick={start}>
                Sign in to Plex
              </Button>
            </div>
          </>
        ) : (
          <>
            <Status state={now.connected ? 'connected' : 'error'}>
              {now.connected
                ? `Connected to ${chosen || 'Plex'}`
                : chosen
                  ? `${chosen} is not answering`
                  : 'Signed in, but no server is chosen'}
            </Status>
            {options.length > 0 && servers(SWITCHES)}
            <LibraryField value={library} libraries={offered} />
            <LibraryStats connected={now.connected} />
            <div className={styles.plex__actions}>
              <Button
                variant="secondary"
                onClick={sync.start}
                disabled={!now.connected || syncing}
              >
                {syncing ? 'Syncing…' : 'Sync library'}
              </Button>
              <Button variant="ghost" onClick={plex.signOut}>
                Sign out
              </Button>
            </div>
          </>
        )}

        {plex.error !== '' && (
          <Text tone="error" role="alert">
            {plex.error}
          </Text>
        )}
      </div>
    </Section>
  )
}
