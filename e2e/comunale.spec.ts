import { expect, test } from '@playwright/test'
import { hold, queryErrors, skipMapTiles } from './helpers'

// The fixtures hold Vacone's addresses, in one GeoParquet file that DuckDB
// reads over HTTP.

test.beforeEach(async ({ page }) => {
  await skipMapTiles(page)
})

test('finds an address and selects it', async ({ page }) => {
  const errors = queryErrors(page)
  await page.goto('/')
  const input = page.getByTestId('address-input')

  await input.fill('VIA SAN GIOVANNI 1')
  const first = page.getByTestId('address-suggestion').first()
  await expect(first).toHaveText('VIA SAN GIOVANNI 1')
  await first.click()
  await expect(input).toHaveValue('VIA SAN GIOVANNI 1')
  expect(errors).toEqual([])
})

test('suggests an address typed before the addresses have loaded', async ({ page }) => {
  const release = await hold(page, '**/e2e-data/anncsu-indirizzi.parquet')
  await page.goto('/')
  const input = page.getByTestId('address-input')

  await input.fill('VIA SAN GIOVANNI 1')
  await expect(page.getByTestId('address-suggestion')).toHaveCount(0)

  release()
  await expect(page.getByTestId('address-suggestion').first()).toHaveText('VIA SAN GIOVANNI 1')
})
