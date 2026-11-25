import { defineConfig } from '@playwright/test'

type Mode = 'nazionale' | 'comunale'

// Each mode is its own production build, served together with the data in
// e2e/fixtures/data, so the tests do not read the public bucket. DuckDB
// still downloads its extensions from extensions.duckdb.org.
function server(mode: Mode, port: number) {
  const outDir = `dist-e2e/${mode}`
  return {
    command:
      `npx vite build --outDir ${outDir} --emptyOutDir` +
      ` && cp -R e2e/fixtures/data ${outDir}/e2e-data` +
      ` && npx vite preview --outDir ${outDir} --port ${port} --strictPort`,
    url: `http://localhost:${port}/`,
    env: {
      VITE_APP_MODE: mode,
      VITE_COMUNE_NAME: mode === 'comunale' ? 'del Comune di Vacone' : 'del territorio nazionale',
      VITE_DATA_BASE_URL: `http://localhost:${port}/e2e-data`,
    },
    // Always build: a server left running would test an older build.
    reuseExistingServer: false,
    timeout: 120_000,
  }
}

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  expect: { timeout: 30_000 },
  fullyParallel: true,
  // With five browsers at once (the default on a 10-core Mac) one of them
  // sometimes never returns from newContext and the test times out; three
  // ran clean, and finish sooner than five with a one-minute timeout.
  workers: 3,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    // Full Chromium rather than the headless shell, which leaves holes in
    // the map canvas under a scrolled list and so shows bugs that are not
    // there.
    channel: 'chromium',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'nazionale',
      testMatch: ['nazionale.spec.ts', 'theme.spec.ts'],
      use: { baseURL: 'http://localhost:4173' },
    },
    {
      name: 'comunale',
      testMatch: ['comunale.spec.ts', 'theme.spec.ts'],
      use: { baseURL: 'http://localhost:4174' },
    },
  ],
  webServer: [server('nazionale', 4173), server('comunale', 4174)],
})
