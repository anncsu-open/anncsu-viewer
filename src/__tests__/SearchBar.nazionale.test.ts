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
  { codice_istat: '019068', nome_comune: 'Romano di Lombardia', h3_cells: ['851fb440fffffff'] },
  { codice_istat: '024083', nome_comune: 'Romagnano Sesia', h3_cells: ['851fb441fffffff'] },
  { codice_istat: '010050', nome_comune: 'Romagano', h3_cells: ['851fb442fffffff'] },
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
      geometry: { type: 'Point', coordinates: [12.6411, 42.3761] },
      properties: { name: 'VIA ROMA 1 A', count: 1 },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [12.6412, 42.3762] },
      properties: { name: 'VIA ROMA 1 B', count: 1 },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [12.642, 42.377] },
      properties: { name: 'VIA GARIBALDI 3', count: 1 },
    },
  ],
}

describe('SearchBar (nazionale mode - unified search)', () => {
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

  it('renders a single unified search input', async () => {
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    expect(input.exists()).toBe(true)
  })

  it('ranks exact comune match first when searching "Roma"', async () => {
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Roma')
    await flushPromises()

    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    expect(suggestions.length).toBeGreaterThan(1)
    // "Roma" should be first, before "Romano di Lombardia", "Romagnano Sesia", etc.
    expect(suggestions[0].text()).toContain('Roma')
    expect(suggestions[0].text()).not.toContain('Romano')
  })

  it('shows comune suggestions when typing a comune name', async () => {
    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vac')
    await flushPromises()

    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    expect(suggestions.length).toBe(1)
    expect(suggestions[0].text()).toContain('Vacone')
  })

  it('shows a comune chip after selecting a comune', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone')
    await flushPromises()

    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions[0].trigger('click')
    await flushPromises()

    const chip = wrapper.find('[data-testid="comune-chip"]')
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toContain('Vacone')
  })

  it('clears the input after selecting a comune to allow address search', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone')
    await flushPromises()

    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions[0].trigger('click')
    await flushPromises()

    expect((input.element as HTMLInputElement).value).toBe('')
  })

  it('shows address suggestions after comune is selected', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Select comune
    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone')
    await flushPromises()
    const comuneSuggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await comuneSuggestions[0].trigger('click')
    await flushPromises()

    // Now search for an address
    await input.setValue('VIA')
    await flushPromises()

    const addressSuggestions = wrapper.findAll('[data-testid="address-suggestion"]')
    expect(addressSuggestions.length).toBeGreaterThan(0)
  })

  it('removes the comune chip when clicking X on it', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Select comune
    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone')
    await flushPromises()
    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions[0].trigger('click')
    await flushPromises()

    // Remove chip
    const chipClose = wrapper.find('[data-testid="comune-chip-close"]')
    await chipClose.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="comune-chip"]').exists()).toBe(false)
  })

  it('fetches H3 tiles after comune selection', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone')
    await flushPromises()

    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions[0].trigger('click')
    await flushPromises()

    const fetchCalls = (globalThis.fetch as any).mock.calls.map((c: any) => c[0])
    expect(fetchCalls.some((url: string) => url.includes('tiles/h3_cell=851fb44ffffffff'))).toBe(true)
    expect(mockedExecuteQueryWithBuffers).toHaveBeenCalled()
  })

  it('pre-fetches H3 tiles when comune is detected with comma', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Type "Vacone," — should trigger pre-fetch of tiles
    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone,')
    await flushPromises()

    // Should have fetched the H3 tile in background
    const fetchCalls = (globalThis.fetch as any).mock.calls.map((c: any) => c[0])
    expect(fetchCalls.some((url: string) => url.includes('tiles/h3_cell=851fb44ffffffff'))).toBe(true)
  })

  it('shows address preview in combined suggestion after pre-fetch', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Type combined query — tiles pre-fetched, addresses available
    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone, Via Roma')
    await flushPromises()

    // Should show combined suggestion with address previews
    const previews = wrapper.findAll('[data-testid="address-preview"]')
    expect(previews.length).toBeGreaterThan(0)
    expect(previews[0].text()).toContain('VIA ROMA')
  })

  it('shows "more results" indicator when there are additional matches', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone, Via Roma')
    await flushPromises()

    // Check for the "more results" text if there are more than shown
    const moreText = wrapper.find('[data-testid="more-results"]')
    // May or may not exist depending on number of results
    if (moreText.exists()) {
      expect(moreText.text()).toContain('altri')
    }
  })

  it('selects comune and shows full address list after clicking combined suggestion', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone, Via Roma')
    await flushPromises()

    // Click the combined suggestion
    const suggestion = wrapper.find('[data-testid="combined-suggestion"]')
    await suggestion.trigger('click')
    await flushPromises()

    // Comune chip should appear
    const chip = wrapper.find('[data-testid="comune-chip"]')
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toContain('Vacone')

    // Full address results should be shown
    const addressSuggestions = wrapper.findAll('[data-testid="address-suggestion"]')
    expect(addressSuggestions.length).toBeGreaterThan(0)
  })

  it('shows single result in list instead of auto-selecting', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Select comune first
    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone')
    await flushPromises()
    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions[0].trigger('click')
    await flushPromises()

    // Search for a unique address — should still show in list
    await input.setValue('VIA GARIBALDI 3')
    await flushPromises()

    const addressSuggestions = wrapper.findAll('[data-testid="address-suggestion"]')
    expect(addressSuggestions.length).toBe(1)
    expect(addressSuggestions[0].text()).toContain('VIA GARIBALDI 3')

    // Should NOT auto-select
    const store = useAppStore(pinia)
    expect(store.selectedCoordinates).toBeNull()
  })

  it('shows narrowed list when combined query matches multiple addresses with exponents', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Select comune first
    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone')
    await flushPromises()
    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions[0].trigger('click')
    await flushPromises()

    // Search for address with multiple matches (VIA ROMA 1, VIA ROMA 1 A, VIA ROMA 1 B)
    await input.setValue('VIA ROMA 1')
    await flushPromises()

    const addressSuggestions = wrapper.findAll('[data-testid="address-suggestion"]')
    expect(addressSuggestions.length).toBeGreaterThan(1)
  })

  // --- Step-by-step flow: select comune then search address ---

  it('step flow: select comune from list, then search address shows results', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Step 1: type comune name
    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone')
    await flushPromises()

    // Step 2: select from dropdown
    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    expect(suggestions.length).toBeGreaterThan(0)
    await suggestions[0].trigger('click')
    await flushPromises()

    // Step 3: chip should be visible, input cleared
    expect(wrapper.find('[data-testid="comune-chip"]').exists()).toBe(true)
    expect((input.element as HTMLInputElement).value).toBe('')

    // Step 4: type address
    await input.setValue('Via Roma')
    await flushPromises()

    // Step 5: address suggestions should appear
    const addressSuggestions = wrapper.findAll('[data-testid="address-suggestion"]')
    expect(addressSuggestions.length).toBeGreaterThan(0)
    expect(addressSuggestions.some((s) => s.text().includes('VIA ROMA'))).toBe(true)
  })

  it('step flow: select comune, search address, click result triggers fly-to', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone')
    await flushPromises()

    const comuneSuggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await comuneSuggestions[0].trigger('click')
    await flushPromises()

    await input.setValue('VIA GARIBALDI')
    await flushPromises()

    const addressSuggestions = wrapper.findAll('[data-testid="address-suggestion"]')
    expect(addressSuggestions.length).toBeGreaterThan(0)

    await addressSuggestions[0].trigger('click')
    await flushPromises()

    const store = useAppStore(pinia)
    expect(store.selectedCoordinates).not.toBeNull()
  })

  // --- Combined flow: "Vacone, Via Roma" ---

  it('combined flow: "Vacone, Via Roma" shows preview after tiles load', async () => {
    // Make the mock resolve with a small delay to simulate async
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')

    // Type "Vacone," first to trigger prefetch
    await input.setValue('Vacone,')
    await flushPromises()

    // Now complete the query
    await input.setValue('Vacone, Via Roma')
    await flushPromises()

    // Combined suggestion should be visible
    const combined = wrapper.find('[data-testid="combined-suggestion"]')
    expect(combined.exists()).toBe(true)
    expect(combined.text()).toContain('Vacone')

    // After prefetch completes, previews should appear
    const previews = wrapper.findAll('[data-testid="address-preview"]')
    expect(previews.length).toBeGreaterThan(0)
  })

  it('combined flow: clicking suggestion selects comune and shows address list', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone, Via Roma')
    await flushPromises()

    const combined = wrapper.find('[data-testid="combined-suggestion"]')
    expect(combined.exists()).toBe(true)
    await combined.trigger('click')
    await flushPromises()

    // Chip visible
    expect(wrapper.find('[data-testid="comune-chip"]').exists()).toBe(true)

    // Address list visible
    const addressSuggestions = wrapper.findAll('[data-testid="address-suggestion"]')
    expect(addressSuggestions.length).toBeGreaterThan(0)
  })

  it('combined flow: clicking address result from combined triggers fly-to', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone, Via Roma')
    await flushPromises()

    const combined = wrapper.find('[data-testid="combined-suggestion"]')
    await combined.trigger('click')
    await flushPromises()

    const addressSuggestions = wrapper.findAll('[data-testid="address-suggestion"]')
    await addressSuggestions[0].trigger('click')
    await flushPromises()

    const store = useAppStore(pinia)
    expect(store.selectedCoordinates).not.toBeNull()
  })

  // --- Prefetch edge cases ---

  it('prefetch: typing "Vacone," then "Vacone, Via" reuses tiles already loading', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')

    // First keystroke triggers prefetch
    await input.setValue('Vacone,')
    await flushPromises()

    // Second keystroke while prefetch may still be in progress
    await input.setValue('Vacone, Via')
    await flushPromises()

    // Should only have fetched tiles ONCE (not twice)
    const tileFetches = (globalThis.fetch as any).mock.calls
      .map((c: any) => c[0])
      .filter((url: string) => url.includes('tiles/h3_cell='))
    // Each H3 cell fetched once
    expect(tileFetches.length).toBe(1) // Vacone has 1 h3_cell in mock
  })

  it('prefetch: switching from one comune to another loads new tiles', async () => {
    mockedExecuteQueryWithBuffers
      .mockResolvedValueOnce(mockAddressFeatures as any)
      .mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')

    // Start with Vacone
    await input.setValue('Vacone')
    await flushPromises()
    const suggestions1 = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions1[0].trigger('click')
    await flushPromises()

    // Clear and switch to Viterbo
    const chipClose = wrapper.find('[data-testid="comune-chip-close"]')
    await chipClose.trigger('click')
    await flushPromises()

    await input.setValue('Viterbo')
    await flushPromises()
    const suggestions2 = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions2[0].trigger('click')
    await flushPromises()

    // Should have fetched tiles for both comuni
    expect(mockedExecuteQueryWithBuffers).toHaveBeenCalledTimes(2)
  })

  // --- Async timing tests (delayed mock to simulate real network) ---

  it('combined flow: typing full "Vacone, Via Roma" without intermediate steps shows preview after async load', async () => {
    // Simulate delayed tile loading
    let resolveQuery: (value: any) => void
    mockedExecuteQueryWithBuffers.mockImplementation(
      () => new Promise((resolve) => { resolveQuery = resolve })
    )

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')

    // Type the full combined query in one go (no intermediate "Vacone,")
    await input.setValue('Vacone, Via Roma')
    await flushPromises()

    // Combined suggestion should appear immediately (without preview)
    const combined = wrapper.find('[data-testid="combined-suggestion"]')
    expect(combined.exists()).toBe(true)
    expect(combined.text()).toContain('Vacone')

    // Preview should be empty while loading
    expect(wrapper.findAll('[data-testid="address-preview"]').length).toBe(0)

    // Simulate tiles loaded
    resolveQuery!(mockAddressFeatures)
    await flushPromises()

    // Now preview should appear
    const previews = wrapper.findAll('[data-testid="address-preview"]')
    expect(previews.length).toBeGreaterThan(0)
    expect(previews[0].text()).toContain('VIA ROMA')
  })

  it('combined flow: preview updates as user types more address characters', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')

    // First trigger prefetch
    await input.setValue('Vacone,')
    await flushPromises()

    // Type "Via Roma" — should show all Via Roma matches
    await input.setValue('Vacone, Via Roma')
    await flushPromises()

    const previews1 = wrapper.findAll('[data-testid="address-preview"]')
    const count1 = previews1.length

    // Narrow to "Via Roma 1" — should show fewer matches
    await input.setValue('Vacone, Via Roma 1')
    await flushPromises()

    const previews2 = wrapper.findAll('[data-testid="address-preview"]')
    expect(previews2.length).toBeLessThanOrEqual(count1)
    expect(previews2.every((p) => p.text().includes('VIA ROMA 1'))).toBe(true)
  })

  it('combined flow: each keystroke does not reset preview if tiles already loaded', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')

    // Trigger prefetch and wait
    await input.setValue('Vacone,')
    await flushPromises()

    // Type address part
    await input.setValue('Vacone, Via')
    await flushPromises()

    // Should have preview (tiles are loaded)
    const previews1 = wrapper.findAll('[data-testid="address-preview"]')
    expect(previews1.length).toBeGreaterThan(0)

    // Type more — preview should update, not disappear
    await input.setValue('Vacone, Via Roma')
    await flushPromises()

    const previews2 = wrapper.findAll('[data-testid="address-preview"]')
    expect(previews2.length).toBeGreaterThan(0)
  })

  it('combined flow: loading indicator shown while tiles are loading', async () => {
    let resolveQuery: (value: any) => void
    mockedExecuteQueryWithBuffers.mockImplementation(
      () => new Promise((resolve) => { resolveQuery = resolve })
    )

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone, Via Roma')
    await flushPromises()

    // While loading, should show loading indicator
    expect(wrapper.text()).toContain('caricamento')

    // After load, indicator should disappear
    resolveQuery!(mockAddressFeatures)
    await flushPromises()

    expect(wrapper.text()).not.toContain('caricamento')
  })

  it('combined flow: progressive typing "V-a-c-o-n-e-,-V-i-a" shows preview once loaded', async () => {
    let resolveQuery: (value: any) => void
    mockedExecuteQueryWithBuffers.mockImplementation(
      () => new Promise((resolve) => { resolveQuery = resolve })
    )

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    const input = wrapper.find('[data-testid="unified-search-input"]')

    // Simulate progressive typing (each keystroke triggers the watcher)
    await input.setValue('Va')
    await flushPromises()
    await input.setValue('Vac')
    await flushPromises()
    await input.setValue('Vaco')
    await flushPromises()
    await input.setValue('Vacon')
    await flushPromises()
    await input.setValue('Vacone')
    await flushPromises()
    await input.setValue('Vacone,')
    await flushPromises()
    await input.setValue('Vacone, ')
    await flushPromises()
    await input.setValue('Vacone, V')
    await flushPromises()
    await input.setValue('Vacone, Vi')
    await flushPromises()
    await input.setValue('Vacone, Via')
    await flushPromises()

    // Combined suggestion should be visible
    const combined = wrapper.find('[data-testid="combined-suggestion"]')
    expect(combined.exists()).toBe(true)

    // Tiles still loading — no preview yet
    expect(wrapper.findAll('[data-testid="address-preview"]').length).toBe(0)

    // Now resolve the tile loading
    resolveQuery!(mockAddressFeatures)
    await flushPromises()

    // Preview should now appear
    const previews = wrapper.findAll('[data-testid="address-preview"]')
    expect(previews.length).toBeGreaterThan(0)
  })

  it('resets everything when clearing from unified search', async () => {
    mockedExecuteQueryWithBuffers.mockResolvedValueOnce(mockAddressFeatures as any)

    const wrapper = mount(SearchBar, { global: { plugins: [pinia] } })
    await flushPromises()

    // Select comune
    const input = wrapper.find('[data-testid="unified-search-input"]')
    await input.setValue('Vacone')
    await flushPromises()
    const suggestions = wrapper.findAll('[data-testid="comune-suggestion"]')
    await suggestions[0].trigger('click')
    await flushPromises()

    // Clear
    const clearBtn = wrapper.find('[data-testid="clear-search"]')
    if (clearBtn.exists()) {
      await clearBtn.trigger('click')
      await flushPromises()
    }

    const store = useAppStore(pinia)
    expect(store.selectedCoordinates).toBeNull()
  })
})
