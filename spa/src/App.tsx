import { useEffect, useState } from 'react'

/** What the API reported about itself, or why it could not be reached. */
type Health =
  | { status: 'loading' }
  | { status: 'ok'; body: unknown }
  | { status: 'unreachable'; reason: string }

/**
 * The scaffold's only screen: proof the stack is wired.
 *
 * It renders through the ported stylesheet and reads the API through Vite's
 * proxy, so a failure here is the toolchain, not the port that follows.
 */
export default function App() {
  const [health, setHealth] = useState<Health>({ status: 'loading' })

  useEffect(() => {
    const aborter = new AbortController()
    fetch('/api/health', { signal: aborter.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        setHealth({ status: 'ok', body: await response.json() })
      })
      .catch((error: unknown) => {
        if (aborter.signal.aborted) return
        setHealth({ status: 'unreachable', reason: String(error) })
      })
    return () => aborter.abort()
  }, [])

  return (
    <div className="app">
      <header className="header">
        <h1 className="logo">MediaSage</h1>
      </header>
      <main id="main-content">
        <h2>Scaffold</h2>
        {health.status === 'loading' && <p>Reaching the API…</p>}
        {health.status === 'unreachable' && (
          <p style={{ color: 'var(--error)' }}>
            API unreachable: {health.reason}. Start it on port 5765.
          </p>
        )}
        {health.status === 'ok' && (
          <pre style={{ color: 'var(--success)' }}>
            {JSON.stringify(health.body, null, 2)}
          </pre>
        )}
      </main>
    </div>
  )
}
