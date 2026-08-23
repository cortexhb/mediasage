import { useEffect, useState } from 'react'

/** What the API reported about itself, or why it could not be reached. */
type Health =
  | { readonly kind: 'loading' }
  | { readonly kind: 'ok'; readonly body: unknown }
  | { readonly kind: 'unreachable'; readonly reason: string }

/**
 * The scaffold's only screen: proof the stack is wired.
 *
 * It renders through the ported stylesheet and reads the API through Vite's
 * proxy, so a failure here is the toolchain, not the port that follows.
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
    <div className="app">
      <header className="header">
        <h1 className="logo">MediaSage</h1>
      </header>
      <main id="main-content">
        <h2>Scaffold</h2>
        {health.kind === 'loading' && <p>Reaching the API…</p>}
        {health.kind === 'unreachable' && (
          <p style={{ color: 'var(--error)' }}>
            API unreachable: {health.reason}. Start it on port 5765.
          </p>
        )}
        {health.kind === 'ok' && (
          <pre style={{ color: 'var(--success)' }}>
            {JSON.stringify(health.body, null, 2)}
          </pre>
        )}
      </main>
    </div>
  )
}
