import { useEffect, useState } from 'react'

import { Heading } from './components/atoms/Heading/Heading.tsx'
import { Text } from './components/atoms/Text/Text.tsx'
import styles from './App.module.scss'

/** What the API reported about itself, or why it could not be reached. */
type Health =
  | { readonly kind: 'loading' }
  | { readonly kind: 'ok'; readonly body: unknown }
  | { readonly kind: 'unreachable'; readonly reason: string }

/**
 * The scaffold's only screen: proof the stack is wired.
 *
 * It reads the API through Vite's proxy, so a failure here is the toolchain,
 * not the port that follows. Phase 3 replaces it with Home.
 */
export default function App() {
  const [health, setHealth] = useState<Health>({ kind: 'loading' })

  useEffect(() => {
    const aborter = new AbortController()

    const read = async (): Promise<Health> => {
      const response = await fetch('/api/health', { signal: aborter.signal })
      if (!response.ok) {
        throw new Error(`GET /api/health returned ${String(response.status)}`)
      }
      return { kind: 'ok', body: (await response.json()) as unknown }
    }

    read().then(setHealth, (error: unknown) => {
      // An abort is this effect being cleaned up, not a failure. Everything
      // else is put on screen rather than dropped.
      if (aborter.signal.aborted) return
      setHealth({
        kind: 'unreachable',
        reason: error instanceof Error ? error.message : String(error),
      })
    })

    return () => {
      aborter.abort()
    }
  }, [])

  return (
    <>
      <Heading level={2}>Scaffold</Heading>
      {health.kind === 'loading' && <Text>Reaching the API…</Text>}
      {health.kind === 'unreachable' && (
        <Text tone="error" role="alert">
          API unreachable: {health.reason}. Start it on port 5765.
        </Text>
      )}
      {health.kind === 'ok' && (
        <pre className={styles.payload}>
          {JSON.stringify(health.body, null, 2)}
        </pre>
      )}
    </>
  )
}
