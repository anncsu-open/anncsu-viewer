import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock pmtiles
vi.mock('pmtiles', () => ({
  Protocol: vi.fn().mockImplementation(() => ({
    tile: vi.fn(),
  })),
}))

// Mock maplibre-gl
vi.mock('maplibre-gl', () => ({
  default: {
    Map: vi.fn().mockImplementation((opts: any) => ({
      _opts: opts,
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

// Mock config to comunale mode (uses parquet for bounds)
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

// Mock layer service
vi.mock('@/services/layer', () => ({
  addGeoJsonLayerAndReturnLegend: vi.fn(),
}))

import { executeQuery } from '@/services/duckdb'
import { useAppStore } from '@/store/app.store'
import maplibregl from 'maplibre-gl'

const mockedExecuteQuery = vi.mocked(executeQuery)
const MockedMap = vi.mocked(maplibregl.Map)

function makeGeoMetadata(bbox: [number, number, number, number]) {
  return JSON.stringify({
    version: '1.1.0',
    primary_column: 'geometry',
    columns: {
      geometry: {
        encoding: 'WKB',
        bbox,
        geometry_types: ['Point'],
      },
    },
  })
}

function metadataResponse(geoJson: string) {
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [0, 0] },
        properties: { value: geoJson },
      },
    ],
  } as any
}

function minMaxResponse(minX: number, minY: number, maxX: number, maxY: number) {
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [0, 0] },
        properties: { min_x: minX, min_y: minY, max_x: maxX, max_y: maxY },
      },
    ],
  } as any
}

describe('Map', () => {
  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
  })

  it('reads bbox from GeoParquet metadata to set initial bounds', async () => {
    const bbox: [number, number, number, number] = [6.70, 35.50, 18.51, 47.08]

    mockedExecuteQuery.mockImplementation(async (query: string) => {
      if (query.includes('parquet_kv_metadata')) {
        return metadataResponse(makeGeoMetadata(bbox))
      }
      return undefined
    })

    const MapComponent = (await import('@/components/Map.vue')).default
    mount(MapComponent, { global: { plugins: [createPinia()] } })
    await flushPromises()

    expect(mockedExecuteQuery).toHaveBeenCalledWith(
      expect.stringContaining('parquet_kv_metadata'),
    )

    const mapOpts = MockedMap.mock.calls[0]?.[0] as any
    expect(mapOpts.bounds).toEqual([[6.70, 35.50], [18.51, 47.08]])
  })

  it('adapts bounds when GeoParquet bbox changes', async () => {
    const bbox: [number, number, number, number] = [9.0, 44.0, 11.0, 46.0]

    mockedExecuteQuery.mockImplementation(async (query: string) => {
      if (query.includes('parquet_kv_metadata')) {
        return metadataResponse(makeGeoMetadata(bbox))
      }
      return undefined
    })

    const MapComponent = (await import('@/components/Map.vue')).default
    mount(MapComponent, { global: { plugins: [createPinia()] } })
    await flushPromises()

    const mapOpts = MockedMap.mock.calls[0]?.[0] as any
    expect(mapOpts.bounds).toEqual([[9.0, 44.0], [11.0, 46.0]])
  })

  it('falls back to MIN/MAX query when metadata read fails', async () => {
    mockedExecuteQuery.mockImplementation(async (query: string) => {
      if (query.includes('parquet_kv_metadata')) {
        throw new Error('metadata query failed')
      }
      if (query.includes('MIN(longitude)')) {
        return minMaxResponse(7.0, 36.0, 18.0, 47.0)
      }
      return undefined
    })

    const MapComponent = (await import('@/components/Map.vue')).default
    mount(MapComponent, { global: { plugins: [createPinia()] } })
    await flushPromises()

    const mapOpts = MockedMap.mock.calls[0]?.[0] as any
    expect(mapOpts.bounds).toEqual([[7.0, 36.0], [18.0, 47.0]])
  })

  it('adds a highlighted point layer when an address is selected', async () => {
    const bbox: [number, number, number, number] = [6.70, 35.50, 18.51, 47.08]

    mockedExecuteQuery.mockImplementation(async (query: string) => {
      if (query.includes('parquet_kv_metadata')) {
        return metadataResponse(makeGeoMetadata(bbox))
      }
      return undefined
    })

    const MapComponent = (await import('@/components/Map.vue')).default
    const pinia = createPinia()
    mount(MapComponent, { global: { plugins: [pinia] } })
    await flushPromises()

    const mapInstance = MockedMap.mock.results[0].value
    const store = useAppStore(pinia)

    // Select an address
    store.setSelectedCoordinates([12.5, 42.0])
    await flushPromises()

    // Should add a source and layer for the highlighted point
    expect(mapInstance.addSource).toHaveBeenCalledWith(
      'selected-address',
      expect.objectContaining({ type: 'geojson' }),
    )
    expect(mapInstance.addLayer).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'selected-address-point',
        source: 'selected-address',
        type: 'circle',
        paint: expect.objectContaining({
          'circle-color': '#FF6B35',
        }),
      }),
    )
  })

  it('removes the highlighted point when selectedCoordinates becomes null', async () => {
    const bbox: [number, number, number, number] = [6.70, 35.50, 18.51, 47.08]

    mockedExecuteQuery.mockImplementation(async (query: string) => {
      if (query.includes('parquet_kv_metadata')) {
        return metadataResponse(makeGeoMetadata(bbox))
      }
      return undefined
    })

    const MapComponent = (await import('@/components/Map.vue')).default
    const pinia = createPinia()
    mount(MapComponent, { global: { plugins: [pinia] } })
    await flushPromises()

    const mapInstance = MockedMap.mock.results[0].value
    const store = useAppStore(pinia)

    // Mock getLayer/getSource to return true (layer exists)
    mapInstance.getLayer = vi.fn(() => true)
    mapInstance.getSource = vi.fn(() => true)

    // Select then deselect
    store.setSelectedCoordinates([12.5, 42.0])
    await flushPromises()

    store.setSelectedCoordinates(null)
    await flushPromises()

    // Should remove the highlighted layer and source
    expect(mapInstance.removeLayer).toHaveBeenCalledWith('selected-address-point')
    expect(mapInstance.removeSource).toHaveBeenCalledWith('selected-address')
  })

  it('resets map view to default bounds when resetView is triggered', async () => {
    const bbox: [number, number, number, number] = [6.70, 35.50, 18.51, 47.08]

    mockedExecuteQuery.mockImplementation(async (query: string) => {
      if (query.includes('parquet_kv_metadata')) {
        return metadataResponse(makeGeoMetadata(bbox))
      }
      return undefined
    })

    const MapComponent = (await import('@/components/Map.vue')).default
    const pinia = createPinia()
    mount(MapComponent, { global: { plugins: [pinia] } })
    await flushPromises()

    const mapInstance = MockedMap.mock.results[0].value
    const store = useAppStore(pinia)

    // Select an address, then clear
    store.setSelectedCoordinates([12.5, 42.0])
    await flushPromises()

    store.setSelectedCoordinates(null)
    store.triggerResetView()
    await flushPromises()

    // Should call fitBounds with the default bounds
    expect(mapInstance.fitBounds).toHaveBeenCalledWith(
      [[6.70, 35.50], [18.51, 47.08]],
      { padding: 20 },
    )
  })
})
