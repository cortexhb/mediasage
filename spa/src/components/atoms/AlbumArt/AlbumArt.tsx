/**
 * A track's cover, or a letter tile standing in for one.
 *
 * Ports `trackArtHtml` and `artPlaceholderHtml` (`frontend/app.js:203`). The
 * tile's colour is a hash of the artist, so the same artist is always the same
 * colour -- that is a computed value, which is why it is an inline style and
 * not a class.
 *
 * Art that 404s falls back to the tile, as the legacy `onerror` did: the proxy
 * answers per rating key and a key can outlive its thumb.
 */
import { useState } from 'react'

import styles from './AlbumArt.module.scss'

export interface AlbumArtProps {
  /** The proxy URL, absent where Plex has no thumb for the track. */
  readonly src?: string | null | undefined
  readonly artist: string
  readonly album: string
  /** `large` fills its container; the default is the 48px row thumbnail. */
  readonly size?: 'row' | 'large'
}

/** djb2, as `frontend/app.js:196` hashed it. -1 stands for "no artist". */
function artistHue(name: string): number {
  if (!name) return -1
  let hash = 5381
  for (let index = 0; index < name.length; index++)
    hash = ((hash << 5) + hash + name.charCodeAt(index)) >>> 0
  return hash % 360
}

export function AlbumArt({ src, artist, album, size = 'row' }: AlbumArtProps) {
  const [broken, setBroken] = useState(false)

  if (src && !broken)
    return (
      <img
        className={styles.albumArt}
        data-size={size}
        src={src}
        alt={album}
        loading="lazy"
        onError={() => {
          setBroken(true)
        }}
      />
    )

  const hue = artistHue(artist)
  return (
    <div
      className={styles.albumArt__tile}
      data-size={size}
      aria-hidden="true"
      style={{
        backgroundColor:
          hue >= 0 ? `hsl(${String(hue)},30%,20%)` : 'hsl(0,0%,20%)',
        color: hue >= 0 ? `hsl(${String(hue)},40%,60%)` : 'hsl(0,0%,55%)',
      }}
    >
      {artist ? artist.charAt(0).toUpperCase() : '♫'}
    </div>
  )
}
