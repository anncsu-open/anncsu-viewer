import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SearchBar from '@/components/SearchBar.vue'
import { useAppStore } from '@/store/app.store'

// Mock config to comunale mode
vi.mock('@/config', () => ({
  appConfig: {
    comuneName: 'del Comune di Test',
    dataBaseUrl: 'http://localhost:5173',
    appMode: 'comunale',
    isNazionale: false,
  },
}))

// Mock DuckDB executeQuery
vi.mock('@/services/duckdb', () => ({
  executeQuery: vi.fn(),
}))

import { executeQuery } from '@/services/duckdb'
const mockedExecuteQuery = vi.mocked(executeQuery)

// FeatureCollection returned by DuckDB for the address list query
const mockAddressFeatures = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [12.641, 42.376] },
      properties: { name: 'VIA ROMA 1', count: 1 },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [12.642, 42.377] },
      properties: { name: 'VIA ROMA 15', count: 1 },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [12.643, 42.378] },
      properties: { name: 'VIA GARIBALDI 3', count: 1 },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [12.644, 42.379] },
      properties: { name: 'PIAZZA DELLA LIBERTA 7', count: 1 },
    },
  ],
}

describe('SearchBar', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
    mockedExecuteQuery.mockResolvedValue(mockAddressFeatures as any)
  })

  it('is always visible', () => {
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    expect(wrapper.find('input').exists()).toBe(true)
  })

  it('renders search input with label and placeholder', () => {
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    expect(wrapper.find('label').text()).toContain('Cerca indirizzo')
    expect(wrapper.find('input').attributes('placeholder')).toContain('VIA ROMA 15')
  })

  it('loads address list via DuckDB executeQuery on mount', async () => {
    mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(mockedExecuteQuery).toHaveBeenCalled()
    const query = mockedExecuteQuery.mock.calls[0][0]
    expect(query).toContain('read_parquet')
    expect(query).toContain('addresses')
  })

  it('does not use fetch to load addresses', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('does not show autocomplete initially', () => {
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    expect(wrapper.find('.cursor-pointer').exists()).toBe(false)
  })

  it('shows clear button only when searchFilter has value', async () => {
    const store = useAppStore()
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })

    expect(wrapper.find('button').exists()).toBe(false)

    store.setSearchFilter('VIA ROMA')
    await flushPromises()
    expect(wrapper.find('button[title="Clear search"]').exists()).toBe(true)
  })

  it('filters addresses on searchFilter change', async () => {
    const store = useAppStore()
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    store.setSearchFilter('ROMA')
    await flushPromises()

    const items = wrapper.findAll('.cursor-pointer')
    expect(items.length).toBe(2) // VIA ROMA 1, VIA ROMA 15
  })

  it('sets selectedCoordinates in store when address is selected', async () => {
    const store = useAppStore()
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    store.setSearchFilter('ROMA')
    await flushPromises()

    const items = wrapper.findAll('.cursor-pointer')
    await items[0].trigger('click')

    expect(store.selectedCoordinates).toEqual([12.641, 42.376])
  })

  it('sets store query with filter when address is selected', async () => {
    const store = useAppStore()
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    store.setSearchFilter('ROMA')
    await flushPromises()

    const items = wrapper.findAll('.cursor-pointer')
    await items[0].trigger('click')

    expect(store.searchFilter).toBe('VIA ROMA 1')
    expect(store.query).toContain("UPPER(ODONIMO) = 'VIA ROMA'")
    expect(store.query).toContain("CAST(CIVICO AS VARCHAR) = '1'")
  })

  it('onClear resets filter, coordinates and loads all addresses', async () => {
    const store = useAppStore()
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Select an address first
    store.setSearchFilter('ROMA')
    await flushPromises()
    const items = wrapper.findAll('.cursor-pointer')
    await items[0].trigger('click')
    expect(store.selectedCoordinates).not.toBeNull()

    // Clear
    const clearBtn = wrapper.find('button[title="Clear search"]')
    await clearBtn.trigger('click')

    expect(store.searchFilter).toBe('')
    expect(store.selectedCoordinates).toBeNull()
    expect(store.query).not.toContain('UPPER(ODONIMO)')
    expect(store.query).toContain('read_parquet')
  })

  it('onClear triggers resetView to restore default map view', async () => {
    const store = useAppStore()
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Select an address first (zooms in)
    store.setSearchFilter('ROMA')
    await flushPromises()
    const items = wrapper.findAll('.cursor-pointer')
    await items[0].trigger('click')
    expect(store.selectedCoordinates).toEqual([12.641, 42.376])

    // Clear should trigger resetView
    const clearBtn = wrapper.find('button[title="Clear search"]')
    await clearBtn.trigger('click')

    expect(store.resetView).toBe(true)
  })
})
