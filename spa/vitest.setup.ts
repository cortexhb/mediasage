/**
 * Loaded before every test file (see `test.setupFiles` in `vitest.config.ts`).
 *
 * Also owns the mock network. Requests are intercepted at the boundary rather
 * than by replacing `fetch` per test, so the code under test runs the same
 * request path it runs in the browser. Tests register their own handlers with
 * `server.use(...)`, importing it from `@test`.
 *
 * Cleanup is not wired here: with `globals: true`, React Testing Library
 * registers its own `afterEach` teardown against the global hook.
 */
import '@testing-library/jest-dom/vitest'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll } from 'vitest'

export const server = setupServer()

// `error`, not `warn`: a request nobody wrote a handler for is a test that is
// not describing what it exercises.
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
})

afterEach(() => {
  server.resetHandlers()
})

afterAll(() => {
  server.close()
})
