import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { skipMapTiles } from './helpers'

// The look shared with Portolan Browser Italia, checked in both modes.

test.beforeEach(async ({ page }) => {
  await skipMapTiles(page)
})

test('serves its own fonts', async ({ page }) => {
  const requested: string[] = []
  page.on('request', (request) => requested.push(request.url()))
  await page.goto('/')
  await expect(page.locator('nav')).toBeVisible()
  // A string, because the e2e code is type-checked without the DOM library.
  await page.evaluate('document.fonts.ready.then(() => true)')

  // document.fonts.check() is true for Google's Titillium too, so the
  // test looks at where the font came from.
  expect(requested.filter((url) => /fonts\.(googleapis|gstatic)\.com/.test(url))).toEqual([])
  expect(requested.some((url) => url.includes('/assets/titillium-web-latin-600-normal'))).toBe(true)
})

test('is an Italian page with a description', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('html')).toHaveAttribute('lang', 'it')
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    'content',
    /^Cerca e visualizza sulla mappa gli indirizzi e i numeri civici dell'ANNCSU /,
  )
})

test.describe('header', () => {
  async function boxOf(page: Page, selector: string) {
    const box = await page.locator(selector).boundingBox()
    if (!box) throw new Error(`${selector} is not on screen`)
    return box
  }

  async function expectInsideHeader(page: Page) {
    const nav = await boxOf(page, 'nav')
    const name = await boxOf(page, '[data-testid="site-name"]')
    expect(name.y).toBeGreaterThanOrEqual(nav.y)
    expect(name.y + name.height).toBeLessThanOrEqual(nav.y + nav.height)
    expect(name.x + name.width).toBeLessThanOrEqual(nav.x + nav.width)
  }

  test('is 72px high with the name at 24px', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/')
    const name = page.getByTestId('site-name')
    await expect(name).toHaveCSS('font-size', '24px')
    await expect(name).toHaveCSS('font-weight', '600')
    expect((await boxOf(page, 'nav')).height).toBe(72)
    expect((await boxOf(page, '[data-testid="site-logo"]')).height).toBe(40)
  })

  test('fits the name on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    await expect(page.getByTestId('site-name')).toBeVisible()
    expect((await boxOf(page, 'nav')).height).toBe(72)
    expect((await boxOf(page, '[data-testid="site-logo"]')).height).toBe(32)
    await expectInsideHeader(page)
  })

  async function setName(page: Page, name: string) {
    await page.getByTestId('site-name').evaluate((element, text) => {
      element.textContent = text
    }, name)
  }

  const longestName = 'Indirizzi ANNCSU del Comune di San Valentino in Abruzzo Citeriore'

  // Whether the line clamp hides part of the name: the height with the
  // clamp lifted is compared with the height on screen. scrollHeight cannot
  // tell, because Titillium's glyphs overflow leading-tight on any line.
  async function nameIsCut(page: Page) {
    return page.getByTestId('site-name').evaluate((element) => {
      const shown = element.getBoundingClientRect().height
      element.style.setProperty('-webkit-line-clamp', 'none')
      const whole = element.getBoundingClientRect().height
      element.style.removeProperty('-webkit-line-clamp')
      return whole > shown + 1
    })
  }

  test('shows the longest comune name whole on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    await setName(page, longestName)
    await expectInsideHeader(page)
    expect(await nameIsCut(page)).toBe(false)
  })

  test('leaves room for the name next to a wide logo on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    const wideLogo =
      'data:image/svg+xml,' +
      encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="100">' +
          '<rect width="600" height="100" fill="white"/></svg>',
      )
    await page.getByTestId('site-logo').evaluate(async (element, src) => {
      element.setAttribute('src', src)
      await (element as unknown as { decode(): Promise<void> }).decode()
    }, wideLogo)
    await setName(page, longestName)
    expect((await boxOf(page, '[data-testid="site-logo"]')).height).toBe(32)
    await expectInsideHeader(page)
    expect(await nameIsCut(page)).toBe(false)
  })

  test('keeps a name of any length inside it on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    await setName(
      page,
      'Indirizzi ANNCSU del Comune di San Valentino in Abruzzo Citeriore, Provincia di Pescara, Regione Abruzzo',
    )
    expect((await boxOf(page, 'nav')).height).toBe(72)
    await expectInsideHeader(page)
  })

  test('opens the panel below it on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    await page.getByTestId('open-panel').click()
    expect((await boxOf(page, 'aside')).y).toBe(72)
  })
})

test('shows who runs the site in the panel', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/')
  const notice = page.getByTestId('notice')
  await expect(notice).toHaveText('Non è un sito istituzionale · gestito da anncsu-open')
  await notice.scrollIntoViewIfNeeded()
  await expect(notice).toBeInViewport()
})

test('keeps the operator on one line on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 })
  await page.goto('/')
  await page.getByTestId('open-panel').click()
  // "gestito da anncsu-open" breaks after the hyphen unless kept together.
  const operator = page.getByTestId('notice-operator')
  await expect(operator).toHaveText('gestito da anncsu-open')
  const { height, lineHeight } = await operator.evaluate((element) => ({
    height: element.getBoundingClientRect().height,
    lineHeight: parseFloat(element.ownerDocument.defaultView!.getComputedStyle(element).lineHeight),
  }))
  expect(height).toBeLessThanOrEqual(lineHeight + 1)
})

test.describe('search field', () => {
  function searchInput(page: Page) {
    const nazionale = test.info().project.name === 'nazionale'
    return page.getByTestId(nazionale ? 'unified-search-input' : 'address-input')
  }

  async function sizeOf(page: Page, selector: string) {
    const box = await page.locator(selector).boundingBox()
    if (!box) throw new Error(`${selector} is not on screen`)
    return box
  }

  test('has a bottom line only', async ({ page }) => {
    await page.goto('/')
    const input = searchInput(page)
    await expect(input).toHaveCSS('border-top-width', '0px')
    await expect(input).toHaveCSS('border-bottom-width', '1px')
    await expect(input).toHaveCSS('border-bottom-color', 'rgb(163, 163, 163)')
    await expect(input).toHaveCSS('border-radius', '0px')
    await expect(input).toHaveCSS('background-color', 'rgb(255, 255, 255)')
  })

  test('has buttons of at least 24px', async ({ page }) => {
    await page.goto('/')
    await searchInput(page).fill('Vacone')
    const clear = await sizeOf(page, 'button[title="Cancella ricerca"]')
    expect(clear.width).toBeGreaterThanOrEqual(24)
    expect(clear.height).toBeGreaterThanOrEqual(24)

    if (test.info().project.name === 'nazionale') {
      await page.getByTestId('comune-suggestion').filter({ hasText: 'Vacone' }).click()
      const close = await sizeOf(page, '[data-testid="comune-chip-close"]')
      expect(close.width).toBeGreaterThanOrEqual(24)
      expect(close.height).toBeGreaterThanOrEqual(24)
    }
  })
})

test.describe('accessibility', () => {
  const wcag21aa = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

  test('passes an axe audit for WCAG 2.1 AA on a desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/')
    await expect(page.getByTestId('notice')).toBeVisible()
    const { violations } = await new AxeBuilder({ page }).withTags(wcag21aa).analyze()
    expect(violations).toEqual([])
  })

  test('passes an axe audit for WCAG 2.1 AA on a phone with the panel open', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    await page.getByTestId('open-panel').click()
    await expect(page.getByTestId('notice')).toBeAttached()
    const { violations } = await new AxeBuilder({ page }).withTags(wcag21aa).analyze()
    expect(violations).toEqual([])
  })
})
