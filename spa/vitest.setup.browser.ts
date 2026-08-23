/**
 * Loaded before every `*.browser.test.tsx` file, which run in real Chromium.
 *
 * No mock network here. `msw/node` intercepts Node's http stack and does not
 * apply in a browser; a browser test that needs one registers `msw/browser`
 * itself. Nothing does yet -- the browser project exists for platform
 * behaviour, not for data.
 */
import '@testing-library/jest-dom/vitest'
import { beforeEach } from 'vitest'

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean
}

// Input here is real, so React must not demand `act()`.
// Per test, because Testing Library turns it on at import.
beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = false
})
