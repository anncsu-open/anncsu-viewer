import { expect, test } from '@playwright/test'
import { hold, queryErrors, skipMapTiles } from './helpers'

// The fixtures hold Vacone's addresses, in one H3 tile.

test.beforeEach(async ({ page }) => {
  await skipMapTiles(page)
})

test('finds an address in a comune and selects it', async ({ page }) => {
  const errors = queryErrors(page)
  await page.goto('/')
  const input = page.getByTestId('unified-search-input')

  await input.fill('Vacone')
  await page.getByTestId('comune-suggestion').filter({ hasText: 'Vacone' }).click()
  await expect(page.getByTestId('comune-chip')).toContainText('Vacone')

  await input.fill('VIA SAN GIOVANNI 1')
  const first = page.getByTestId('address-suggestion').first()
  await expect(first).toHaveText('VIA SAN GIOVANNI 1')
  await first.click()
  await expect(input).toHaveValue('VIA SAN GIOVANNI 1')
  expect(errors).toEqual([])
})

test('suggests a comune typed before the comuni list arrives', async ({ page }) => {
  const release = await hold(page, '**/comuni-h3.json')
  await page.goto('/')

  await page.getByTestId('unified-search-input').fill('Vacone')
  await expect(page.getByTestId('comune-suggestion')).toHaveCount(0)

  release()
  await expect(page.getByTestId('comune-suggestion')).toHaveText(['Vacone'])
})

test('suggests addresses typed while the comune is loading', async ({ page }) => {
  const errors = queryErrors(page)
  const comuni = page.waitForResponse('**/comuni-h3.json')
  await page.goto('/')
  await comuni
  const input = page.getByTestId('unified-search-input')
  await input.fill('Vacone')

  const release = await hold(page, '**/tiles/**')
  await page.getByTestId('comune-suggestion').filter({ hasText: 'Vacone' }).click()
  await input.fill('VIA SAN GIOVANNI 1')
  await expect(page.getByTestId('address-suggestion')).toHaveCount(0)

  release()
  await expect(page.getByTestId('address-suggestion').first()).toHaveText('VIA SAN GIOVANNI 1')
  expect(errors).toEqual([])
})
