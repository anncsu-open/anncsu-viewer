import type { Page } from '@playwright/test'

/**
 * Hold the responses to the requests matching `url` until the returned
 * function is called. The page's routes also see the requests that DuckDB
 * makes from its worker.
 */
export async function hold(page: Page, url: string) {
  let release!: () => void
  const released = new Promise<void>((resolve) => (release = resolve))
  await page.route(url, async (route) => {
    await released
    await route.continue()
  })
  return release
}

/** The DuckDB query errors the page logs, as SearchBar and Map report them. */
export function queryErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error' && message.text().includes('Error executing query')) {
      errors.push(message.text())
    }
  })
  return errors
}

/** The searches are about the data: no basemap and no national PMTiles. */
export async function skipMapTiles(page: Page) {
  await page.route('https://tile.openstreetmap.org/**', (route) => route.abort())
  await page.route('**/anncsu-indirizzi.pmtiles', (route) => route.abort())
}
