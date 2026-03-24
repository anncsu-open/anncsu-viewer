import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock pmtiles
vi.mock('pmtiles', () => ({
  Protocol: vi.fn().mockImplementation(() => ({ tile: vi.fn() })),
}))

// Mock maplibre-gl
vi.mock('maplibre-gl', () => ({
  default: {
    Map: vi.fn().mockImplementation(() => ({
      flyTo: vi.fn(),
      fitBounds: vi.fn(),
      addControl: vi.fn(),
      addSource: vi.fn(),
      addLayer: vi.fn(),
      getLayer: vi.fn(() => false),
      getSource: vi.fn(() => false),
      removeLayer: vi.fn(),
      removeSource: vi.fn(),
      getCanvas: vi.fn(() => ({ style: {} })),
      on: vi.fn(),
    })),
    NavigationControl: vi.fn(),
    Popup: vi.fn().mockImplementation(() => ({
      setLngLat: vi.fn().mockReturnThis(),
      setHTML: vi.fn().mockReturnThis(),
      addTo: vi.fn().mockReturnThis(),
      remove: vi.fn(),
    })),
    addProtocol: vi.fn(),
  },
}))

// Mock config to nazionale mode
vi.mock('@/config', () => ({
  appConfig: {
    comuneName: 'del territorio nazionale',
    dataBaseUrl: 'http://localhost:5173',
    appMode: 'nazionale',
    isNazionale: true,
  },
}))

// Mock DuckDB
vi.mock('@/services/duckdb', () => ({
  executeQuery: vi.fn(),
  executeQueryWithBuffers: vi.fn(),
}))

// Mock layer service
vi.mock('@/services/layer', () => ({
  addGeoJsonLayerAndReturnLegend: vi.fn(),
}))

import SearchBar from '@/components/SearchBar.vue'
import App from '@/App.vue'

describe('Responsive layout', () => {
  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('comuni-h3.json')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
      }
      return Promise.resolve({ ok: true, arrayBuffer: () => Promise.resolve(new ArrayBuffer(8)) })
    }) as any
  })

  describe('SearchBar', () => {
    it('does not use a fixed pixel width', async () => {
      const wrapper = mount(SearchBar, { global: { plugins: [createPinia()] } })
      await flushPromises()

      const container = wrapper.find('[class*="z-20"]')
      const classes = container.classes()
      // Should NOT have a fixed width like w-[28rem]
      const hasFixedWidth = classes.some((c) => /^w-\[\d+rem\]$/.test(c))
      expect(hasFixedWidth).toBe(false)
    })

    it('has a max-width constraint', async () => {
      const wrapper = mount(SearchBar, { global: { plugins: [createPinia()] } })
      await flushPromises()

      const container = wrapper.find('[class*="z-20"]')
      const classes = container.classes()
      const hasMaxWidth = classes.some((c) => c.startsWith('max-w-'))
      expect(hasMaxWidth).toBe(true)
    })

    it('uses relative width for mobile screens', async () => {
      const wrapper = mount(SearchBar, { global: { plugins: [createPinia()] } })
      await flushPromises()

      const container = wrapper.find('[class*="z-20"]')
      const classes = container.classes()
      // Should have a percentage or calc-based width
      const hasRelativeWidth = classes.some(
        (c) => c.startsWith('w-[calc') || c.startsWith('w-full') || c.startsWith('w-11/12') || c.startsWith('w-[95')
      )
      expect(hasRelativeWidth).toBe(true)
    })
  })

  describe('App layout', () => {
    it('sidebar is an overlay on mobile (fixed/absolute positioning)', async () => {
      const wrapper = mount(App, { global: { plugins: [createPinia()] } })
      await flushPromises()

      const aside = wrapper.find('aside')
      if (aside.exists()) {
        const classes = aside.classes()
        // On mobile: overlay (fixed or absolute), on desktop: inline (md:relative or md:static)
        const hasOverlayPosition = classes.some(
          (c) => c === 'fixed' || c === 'absolute',
        )
        expect(hasOverlayPosition).toBe(true)
      }
    })

    it('sidebar has a close button inside it', async () => {
      const wrapper = mount(App, { global: { plugins: [createPinia()] } })
      await flushPromises()

      const aside = wrapper.find('aside')
      if (aside.exists()) {
        const closeBtn = aside.find('[data-testid="close-panel"]')
        expect(closeBtn.exists()).toBe(true)
      }
    })

    it('sidebar is closed by default on mobile (window.innerWidth < 768)', async () => {
      // Simulate mobile viewport
      const original = window.innerWidth
      Object.defineProperty(window, 'innerWidth', { value: 375, writable: true, configurable: true })

      vi.resetModules()
      const { createPinia: createPinia2, setActivePinia: setActivePinia2 } = await import('pinia')
      const pinia = createPinia2()
      setActivePinia2(pinia)
      const { useAppStore } = await import('@/store/app.store')
      const store = useAppStore()

      expect(store.sidebarOpen).toBe(false)

      // Restore
      Object.defineProperty(window, 'innerWidth', { value: original, writable: true, configurable: true })
    })

    it('burger button is in the header', async () => {
      const wrapper = mount(App, { global: { plugins: [createPinia()] } })
      await flushPromises()

      const header = wrapper.find('header')
      const burgerBtn = header.find('[data-testid="open-panel"]')
      expect(burgerBtn.exists()).toBe(true)
    })

    it('clicking close button inside panel closes it', async () => {
      const wrapper = mount(App, { global: { plugins: [createPinia()] } })
      await flushPromises()

      const store = (await import('@/store/app.store')).useAppStore()
      store.sidebarOpen = true
      await flushPromises()

      const aside = wrapper.find('aside')
      const closeBtn = aside.find('[data-testid="close-panel"]')
      await closeBtn.trigger('click')
      await flushPromises()

      expect(store.sidebarOpen).toBe(false)
    })

    it('sidebar has scrollable content with overflow', async () => {
      const wrapper = mount(App, { global: { plugins: [createPinia()] } })
      await flushPromises()

      const store = (await import('@/store/app.store')).useAppStore()
      store.sidebarOpen = true
      await flushPromises()

      const aside = wrapper.find('aside')
      if (aside.exists()) {
        const classes = aside.classes()
        const hasOverflow = classes.some(
          (c) => c === 'overflow-y-auto' || c === 'overflow-auto',
        )
        expect(hasOverflow).toBe(true)
      }
    })
  })

  describe('Header', () => {
    it('title text scales down on small screens', async () => {
      const { default: Header } = await import('@/components/Header.vue')
      const wrapper = mount(Header, { global: { plugins: [createPinia()] } })

      const title = wrapper.find('span')
      const classes = title.classes()
      // Should have responsive text size (text-lg on mobile, text-2xl on md+)
      const hasResponsiveText = classes.some((c) => c.startsWith('md:text-') || c.startsWith('lg:text-'))
      expect(hasResponsiveText).toBe(true)
    })
  })
})
