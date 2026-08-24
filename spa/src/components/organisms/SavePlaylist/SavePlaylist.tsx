/**
 * Writing the playlist to Plex, in whichever of the three ways is chosen.
 *
 * Ports the split button and its mode menu (`frontend/index.html:432`,
 * `frontend/app.js:3594`). Choosing a mode changes what the header shows:
 * `PlaylistPicker` stands in for the name field for replace and append.
 *
 * The button's label changes with the mode, and the append label counts the
 * tracks it would add (`frontend/app.js:3586`).
 */
import { useState } from 'react'

import { Button } from '../../atoms/Button/Button.tsx'
import styles from './SavePlaylist.module.scss'

export type SaveMode = 'new' | 'replace' | 'append'

const MODES: readonly { readonly mode: SaveMode; readonly label: string }[] = [
  { mode: 'new', label: 'Save new playlist' },
  { mode: 'replace', label: 'Replace a playlist' },
  { mode: 'append', label: 'Append to a playlist' },
]

export interface SavePlaylistProps {
  readonly mode: SaveMode
  readonly onMode: (mode: SaveMode) => void
  /** How many tracks would be written, for the append label. */
  readonly count: number
  readonly disabled: boolean
}

/** What the main button says, as `frontend/app.js:3613` worded each mode. */
function label(mode: SaveMode, count: number): string {
  if (mode === 'replace') return 'Replace all tracks'
  if (mode === 'append')
    return `Add ${String(count)} track${count === 1 ? '' : 's'}`
  return 'Save to Plex'
}

export function SavePlaylist({
  mode,
  onMode,
  count,
  disabled,
}: SavePlaylistProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className={styles.savePlaylist}>
      <input type="hidden" name="mode" value={mode} />
      <Button type="submit" variant="primary" disabled={disabled}>
        {label(mode, count)}
      </Button>
      <button
        type="button"
        className={styles.savePlaylist__arrow}
        aria-label="Save mode options"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open)
        }}
      >
        ▾
      </button>
      {open && (
        <div className={styles.savePlaylist__menu} role="menu">
          {MODES.map((choice) => (
            <button
              key={choice.mode}
              type="button"
              role="menuitem"
              className={styles.savePlaylist__option}
              aria-current={choice.mode === mode}
              onClick={() => {
                onMode(choice.mode)
                setOpen(false)
              }}
            >
              <span className={styles.savePlaylist__check} aria-hidden="true">
                {choice.mode === mode ? '✓' : ''}
              </span>
              {choice.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
