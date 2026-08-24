/**
 * The link that opens a saved playlist on the Plex server.
 *
 * Ports `.btn-plex` (`frontend/index.html:489`), which both save dialogs
 * carry. Renders nothing without a URL: legacy hides the button then, because
 * the backend omits the URL when it could not build one.
 */
import styles from './OpenInPlex.module.scss'

export interface OpenInPlexProps {
  readonly url?: string | null | undefined
}

export function OpenInPlex({ url }: OpenInPlexProps) {
  if (!url) return null

  return (
    <a className={styles.openInPlex} href={url} target="_blank" rel="noopener">
      Open in Plex
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6" />
        <path d="m21 3-9 9" />
        <path d="M15 3h6v6" />
      </svg>
    </a>
  )
}
