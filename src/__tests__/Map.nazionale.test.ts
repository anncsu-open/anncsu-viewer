import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock pmtiles
vi.mock('pmtiles', () => ({
  Protocol: vi.fn().mockImplementation(() => ({
    tile: vi.fn(),
  })),
  PMTiles: vi.fn().mockImplementation(() => ({
    getHeader: vi.fn().mockResolvedValue({
      minLon: 6.63,
      minLat: 35.49,
      maxLon: 18.52,
      maxLat: 47.09,
    }),
  })),
}))

let mockMapInstance: any

// Mock maplibre-gl
vi.mock('maplibre-gl', () => ({
  default: {
    Map: vi.fn().mockImplementation((opts: any) => {
      mockMapInstance = {
        _opts: opts,
        _onHandlers: {} as Record<string, Function>,
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
        on: vi.fn((event: string, layerOrCb: string | Function, cb?: Function) => {
          const key = cb ? `${event}:${layerOrCb}` : event
          const handler = cb || layerOrCb
          mockMapInstance._onHandlers[key] = handler
        }),
      }
      return mockMapInstance
    }),
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
    dataBaseUrl: 'https://example.r2.dev',
    appMode: 'nazionale',
    isNazionale: true,
  },
}))

// Mock DuckDB (not used in nazionale for map)
vi.mock('@/services/duckdb', () => ({
  executeQuery: vi.fn(),
}))

// Mock layer service
vi.mock('@/services/layer', () => ({
  addGeoJsonLayerAndReturnLegend: vi.fn(),
}))

describe('Map (nazionale mode)', () => {
  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
    mockMapInstance = null
  })

  it('uses data-driven color for PMTiles layer based on out_of_bounds', async () => {
    const MapComponent = (await import('@/components/Map.vue')).default
    mount(MapComponent, { global: { plugins: [createPinia()] } })
    await flushPromises()

    // Trigger the 'load' event handler
    const loadHandler = mockMapInstance._onHandlers['load']
    expect(loadHandler).toBeDefined()
    loadHandler()

    // Check that addLayer was called with data-driven circle-color
    const addLayerCalls = mockMapInstance.addLayer.mock.calls
    const pointsLayer = addLayerCalls.find((call: any) => call[0].id === 'places-points')
    expect(pointsLayer).toBeDefined()

    const paint = pointsLayer[0].paint
    const circleColor = paint['circle-color']

    // Should be a data-driven expression, not a static color
    expect(Array.isArray(circleColor)).toBe(true)
    // Should reference out_of_bounds property
    expect(JSON.stringify(circleColor)).toContain('out_of_bounds')
  })

  it('uses red color for out-of-bounds points', async () => {
    const MapComponent = (await import('@/components/Map.vue')).default
    mount(MapComponent, { global: { plugins: [createPinia()] } })
    await flushPromises()

    const loadHandler = mockMapInstance._onHandlers['load']
    loadHandler()

    const addLayerCalls = mockMapInstance.addLayer.mock.calls
    const pointsLayer = addLayerCalls.find((call: any) => call[0].id === 'places-points')
    const circleColor = pointsLayer[0].paint['circle-color']

    // The expression should contain a red-ish color for out_of_bounds=true
    const colorStr = JSON.stringify(circleColor)
    expect(colorStr).toContain('#E63946') // red for out-of-bounds
    expect(colorStr).toContain('#4c9b82') // green for valid
  })

  it('shows out-of-bounds warning with distance in popup', async () => {
    const MapComponent = (await import('@/components/Map.vue')).default
    mount(MapComponent, { global: { plugins: [createPinia()] } })
    await flushPromises()

    const loadHandler = mockMapInstance._onHandlers['load']
    loadHandler()

    const mousemoveHandler = mockMapInstance._onHandlers['mousemove:places-points']
    expect(mousemoveHandler).toBeDefined()

    // Simulate hovering over an out-of-bounds point with distance
    const mockEvent = {
      features: [{
        properties: {
          ODONIMO: 'VIA FONTANA',
          CIVICO: '7',
          ESPONENTE: null,
          NOME_COMUNE: 'Roccafiorita',
          out_of_bounds: true,
          oob_distance_m: 5978.0,
        },
      }],
      lngLat: { lng: 12.681, lat: 41.806 },
    }

    mousemoveHandler(mockEvent)

    const popupInstance = vi.mocked(
      (await import('maplibre-gl')).default.Popup
    ).mock.results[0].value
    const setHTMLCall = popupInstance.setHTML.mock.calls[0][0]
    expect(setHTMLCall).toContain('VIA FONTANA')
    expect(setHTMLCall).toContain('Fuori confine comunale')
    expect(setHTMLCall).toContain('5978m')
  })

  it('shows out-of-bounds warning without distance when oob_distance_m is missing', async () => {
    const MapComponent = (await import('@/components/Map.vue')).default
    mount(MapComponent, { global: { plugins: [createPinia()] } })
    await flushPromises()

    const loadHandler = mockMapInstance._onHandlers['load']
    loadHandler()

    const mousemoveHandler = mockMapInstance._onHandlers['mousemove:places-points']

    const mockEvent = {
      features: [{
        properties: {
          ODONIMO: 'VIA TEST',
          CIVICO: '1',
          ESPONENTE: null,
          NOME_COMUNE: 'Test',
          out_of_bounds: true,
        },
      }],
      lngLat: { lng: 12.0, lat: 42.0 },
    }

    mousemoveHandler(mockEvent)

    const popupInstance = vi.mocked(
      (await import('maplibre-gl')).default.Popup
    ).mock.results[0].value
    const setHTMLCall = popupInstance.setHTML.mock.calls[0][0]
    expect(setHTMLCall).toContain('Fuori confine comunale')
    expect(setHTMLCall).not.toContain('NaN')
  })

  it('does not show out-of-bounds warning for valid addresses', async () => {
    const MapComponent = (await import('@/components/Map.vue')).default
    mount(MapComponent, { global: { plugins: [createPinia()] } })
    await flushPromises()

    const loadHandler = mockMapInstance._onHandlers['load']
    loadHandler()

    const mousemoveHandler = mockMapInstance._onHandlers['mousemove:places-points']

    const mockEvent = {
      features: [{
        properties: {
          ODONIMO: 'VIA ROMA',
          CIVICO: '1',
          ESPONENTE: null,
          NOME_COMUNE: 'Roma',
          out_of_bounds: false,
          oob_distance_m: null,
        },
      }],
      lngLat: { lng: 12.49, lat: 41.89 },
    }

    mousemoveHandler(mockEvent)

    const popupInstance = vi.mocked(
      (await import('maplibre-gl')).default.Popup
    ).mock.results[0].value
    const setHTMLCall = popupInstance.setHTML.mock.calls[0][0]
    expect(setHTMLCall).toContain('VIA ROMA')
    expect(setHTMLCall).not.toContain('Fuori confine comunale')
  })
})
