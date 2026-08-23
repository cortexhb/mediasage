import { fileURLToPath } from 'node:url'

import { playwright } from '@vitest/browser-playwright'
import { defineConfig, mergeConfig } from 'vitest/config'

import viteConfig from './vite.config.ts'

/**
 * Test configuration, merged onto the app's Vite config so plugins and
 * resolution stay identical between what ships and what is tested.
 *
 * Two projects. Almost everything runs in `unit`, under jsdom, because it is
 * fast and nothing there needs a real engine. A `*.browser.test.tsx` file runs
 * in `dom`, under real Chromium, and exists only for behaviour a DOM emulator
 * does not implement.
 *
 * The one case today is native `<dialog>`. jsdom 30.0.1 declares
 * `HTMLDialogElement` but implements none of `show`, `showModal` or `close`,
 * and happy-dom's `showModal` is `setAttribute('open', '')` -- no focus
 * management, no inertness. Shimming either one would mean asserting against
 * the shim, so `atoms/Overlay` is verified where the behaviour is real.
 */
const shared = {
  // On, so React Testing Library finds the global `afterEach` it registers
  // its automatic cleanup against. Test files still import what they use.
  globals: true,
  // Modules are processed, so a component's `.module.scss` import resolves
  // to real class names in tests instead of undefined.
  css: true,
  restoreMocks: true,
  unstubEnvs: true,
  unstubGlobals: true,
}

const BROWSER_TESTS = 'src/**/*.browser.test.{ts,tsx}'
const UNIT_TESTS = 'src/**/*.test.{ts,tsx}'

export default mergeConfig(
  viteConfig,
  defineConfig({
    resolve: {
      alias: {
        // Tests reach the mock network through this rather than climbing out
        // of `src/` with a chain of `../`.
        '@test': fileURLToPath(new URL('./vitest.setup.ts', import.meta.url)),
      },
    },
    test: {
      coverage: {
        provider: 'v8',
        include: ['src/**/*.{ts,tsx}'],
        exclude: ['src/api/generated/**', 'src/main.tsx'],
      },
      projects: [
        {
          extends: true,
          test: {
            ...shared,
            name: 'unit',
            environment: 'jsdom',
            setupFiles: ['./vitest.setup.ts'],
            include: [UNIT_TESTS],
            // Spelled out because overriding it drops Vitest's own defaults,
            // node_modules included.
            exclude: ['**/node_modules/**', 'dist/**', BROWSER_TESTS],
          },
        },
        {
          extends: true,
          test: {
            ...shared,
            name: 'dom',
            include: [BROWSER_TESTS],
            setupFiles: ['./vitest.setup.browser.ts'],
            browser: {
              enabled: true,
              provider: playwright(),
              headless: true,
              instances: [{ browser: 'chromium' }],
            },
          },
        },
      ],
    },
  }),
)
