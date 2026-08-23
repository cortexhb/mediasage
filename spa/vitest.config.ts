import { fileURLToPath } from 'node:url'

import { defineConfig, mergeConfig } from 'vitest/config'

import viteConfig from './vite.config.ts'

/**
 * Test configuration, merged onto the app's Vite config so plugins and
 * resolution stay identical between what ships and what is tested.
 */
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
      // On, so React Testing Library finds the global `afterEach` it registers
      // its automatic cleanup against. Test files still import what they use.
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./vitest.setup.ts'],
      // Modules are processed, so a component's `.module.scss` import resolves
      // to real class names in tests instead of undefined.
      css: true,
      restoreMocks: true,
      unstubEnvs: true,
      unstubGlobals: true,
      coverage: {
        provider: 'v8',
        include: ['src/**/*.{ts,tsx}'],
        exclude: ['src/api/generated/**', 'src/main.tsx'],
      },
    },
  }),
)
