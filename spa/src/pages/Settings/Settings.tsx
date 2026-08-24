/**
 * Settings — the only place the app is configured.
 *
 * The legacy setup wizard is gone (see `spa/docs/migration.md`), so this
 * screen has to configure a system from nothing. `MediasageConfig` has ten
 * sections, so it is a rail of groups over a pane rather than one long form:
 * each group is its own route and its own save, and a save carries only the
 * fields on screen.
 *
 * The loader fills every group at once — one config read, not five — and the
 * groups read it from `useOutletContext`. It also reads the API's schema,
 * which is where the fields themselves come from; see `libs/patchFields`.
 */
import { Outlet, useLoaderData } from 'react-router'

import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { StorageWarning } from '../../components/molecules/StorageWarning/StorageWarning.tsx'
import { SettingsRail } from '../../components/organisms/SettingsRail/SettingsRail.tsx'
import type { SettingsData } from '../../libs/loadSettings/loadSettings.ts'
import styles from './Settings.module.scss'

export function Settings() {
  const loaded = useLoaderData<SettingsData>()

  return (
    <div className={styles.settings}>
      <Heading level={2}>Settings</Heading>

      <StorageWarning
        writable={loaded.setup.data_dir_writable}
        directory={loaded.setup.data_dir}
        uid={loaded.setup.process_uid}
        gid={loaded.setup.process_gid}
      />

      <div className={styles.settings__panes}>
        <SettingsRail />
        <div className={styles.settings__pane}>
          <Outlet context={loaded} />
        </div>
      </div>
    </div>
  )
}
