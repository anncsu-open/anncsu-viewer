import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAppStore } from '@/store/app.store'

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

import { executeQuery, executeQueryWithBuffers } from '@/services/duckdb'
import SearchBar from '@/components/SearchBar.vue'

const mockedExecuteQuery = vi.mocked(executeQuery)
const mockedExecuteQueryWithBuffers = vi.mocked(executeQueryWithBuffers)

// Mock comuni-h3.json fetch response
const mockComuni = [
  { codice_istat: '058091', nome_comune: 'Roma', h3_cells: ['851fb467fffffff'] },
  { codice_istat: '057072', nome_comune: 'Vacone', h3_cells: ['851fb44ffffffff'] },
  { codice_istat: '056059', nome_comune: 'Viterbo', h3_cells: ['851fb443fffffff'] },
]

// Mock address results after comune selection
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
      properties: { name: 'VIA GARIBALDI 3', count: 1 },
    },
  ],
}

describe('SearchBar (nazionale mode)', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()

    // Mock fetch: comuni-h3.json and H3 tile parquet files
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('comuni-h3.json')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockComuni),
        })
      }
      // H3 tile fetch returns a fake ArrayBuffer
      return Promise.resolve({
        ok: true,
        arrayBuffer: () => Promise.resolve(new ArrayBuffer(8)),
      })
    }) as any
  })

  it('does not load all addresses via DuckDB on mount', async () => {
    mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(mockedExecuteQuery).not.toHaveBeenCalled()
  })

  it('loads comuni list via fetch on mount', async () => {
    mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('comuni-h3.json'),
    )
  })

  it('renders a comune selector input', async () => {
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const comuneInput = wrapper.find('[data-testid="comune-input"]')
    expect(comuneInput.exists()).toBe(true)
  })

  it('renders address input disabled until comune is selected', async () => {
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const addressInput = wrapper.find('[data-testid="address-input"]')
    expect(addressInput.exists()).toBe(true)
    expect((addressInput.element as HTMLInputElement).disabled).toBe(true)
  })

  it('filters comuni on input', async () => {
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const comuneInput = wrapper.find('[data-testid="comune-input"]')
    await comuneInput.setValue('Vac')
    await flushPromises()

    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    expect(suggestions.length).toBe(1)
    expect(suggestions[0].text()).toBe('Vacone')
  })

  it('enables address input after comune is selected', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Type and select a comune
    const comuneInput = wrapper.find('[data-testid="comune-input"]')
    await comuneInput.setValue('Vacone')
    await flushPromises()

    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions[0].trigger('click')
    await flushPromises()

    const addressInput = wrapper.find('[data-testid="address-input"]')
    expect((addressInput.element as HTMLInputElement).disabled).toBe(false)
  })

  it('fetches H3 tiles and queries DuckDB with buffers after comune selection', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const comuneInput = wrapper.find('[data-testid="comune-input"]')
    await comuneInput.setValue('Vacone')
    await flushPromises()

    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions[0].trigger('click')
    await flushPromises()

    // Should have fetched the H3 tile
    const fetchCalls = (globalThis.fetch as any).mock.calls.map((c: any) => c[0])
    expect(fetchCalls.some((url: string) => url.includes('tiles/h3_cell=851fb44ffffffff'))).toBe(true)

    // Should have called executeQueryWithBuffers with CODICE_ISTAT filter
    expect(mockedExecuteQueryWithBuffers).toHaveBeenCalled()
    const query = mockedExecuteQueryWithBuffers.mock.calls[0][0]
    expect(query).toContain("CODICE_ISTAT = '057072'")
  })
})
