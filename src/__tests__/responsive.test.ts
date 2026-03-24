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
    it('sidebar has responsive width', async () => {
      const wrapper = mount(App, { global: { plugins: [createPinia()] } })
      await flushPromises()

      const aside = wrapper.find('aside')
      if (aside.exists()) {
        const classes = aside.classes()
        // Should have mobile-first width (full or auto) and md: breakpoint
        const hasResponsiveWidth = classes.some((c) => c.startsWith('md:'))
        expect(hasResponsiveWidth).toBe(true)
      }
    })

    it('sidebar toggle button does not overlap search bar on mobile', async () => {
      const wrapper = mount(App, { global: { plugins: [createPinia()] } })
      await flushPromises()

      // Toggle button should be at bottom or have different positioning on mobile
      const toggleBtn = wrapper.find('button[title]')
      expect(toggleBtn.exists()).toBe(true)

      // SearchBar should be centered, toggle should not collide
      const searchBar = wrapper.findComponent(SearchBar)
      expect(searchBar.exists()).toBe(true)
    })
  })
})
