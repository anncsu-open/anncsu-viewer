import { describe, it, expect, vi, beforeEach } from 'vitest'
import { colors, addGeoJsonLayerAndReturnLegend } from '@/services/layer'
import type { FeatureCollection } from 'geojson'

vi.mock('@/services/duckdb', () => ({
  executeQuery: vi.fn(),
}))

import { executeQuery } from '@/services/duckdb'
const mockedExecuteQuery = vi.mocked(executeQuery)

function createMockMap() {
  return {
    getLayer: vi.fn().mockReturnValue(false),
    getSource: vi.fn().mockReturnValue(false),
    removeLayer: vi.fn(),
    removeSource: vi.fn(),
    addSource: vi.fn(),
    addLayer: vi.fn(),
  } as any
}

function createFeatureCollection(geometryType: string, counts: number[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: counts.map((count) => ({
      type: 'Feature',
      geometry: { type: geometryType, coordinates: geometryType === 'Point' ? [12, 42] : [[[12, 42], [13, 42], [13, 43], [12, 42]]] },
      properties: { count },
    })),
  } as FeatureCollection
}

describe('colors', () => {
  it('has 7 color entries', () => {
    expect(colors).toHaveLength(7)
  })

  it('all entries are valid hex colors', () => {
    for (const c of colors) {
      expect(c).toMatch(/^#[0-9a-f]{6}$/i)
    }
  })
})

describe('addGeoJsonLayerAndReturnLegend', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns undefined when executeQuery returns undefined', async () => {
    mockedExecuteQuery.mockResolvedValue(undefined)
    const map = createMockMap()
    const result = await addGeoJsonLayerAndReturnLegend(map, 'SELECT 1')
    expect(result).toBeUndefined()
    expect(map.addSource).not.toHaveBeenCalled()
  })

  it('adds a circle layer for Point geometries', async () => {
    mockedExecuteQuery.mockResolvedValue(createFeatureCollection('Point', [1, 2, 3]) as any)
    const map = createMockMap()
    await addGeoJsonLayerAndReturnLegend(map, 'SELECT 1')

    expect(map.addSource).toHaveBeenCalledWith('places-area-sources', expect.objectContaining({ type: 'geojson' }))
    expect(map.addLayer).toHaveBeenCalledWith(expect.objectContaining({ id: 'places-points', type: 'circle' }))
  })

  it('adds a fill layer for Polygon geometries', async () => {
    mockedExecuteQuery.mockResolvedValue(createFeatureCollection('Polygon', [1, 5, 10]) as any)
    const map = createMockMap()
    await addGeoJsonLayerAndReturnLegend(map, 'SELECT 1')

    expect(map.addLayer).toHaveBeenCalledWith(expect.objectContaining({ id: 'places-area', type: 'fill' }))
  })

  it('returns a colorGradient array with threshold/color pairs', async () => {
    mockedExecuteQuery.mockResolvedValue(createFeatureCollection('Polygon', [1, 10, 100]) as any)
    const map = createMockMap()
    const result = await addGeoJsonLayerAndReturnLegend(map, 'SELECT 1')

    expect(result).toBeDefined()
    expect(result!.length).toBe(colors.length * 2)
    // Even indices are thresholds (numbers), odd indices are colors (strings)
    for (let i = 0; i < result!.length; i += 2) {
      expect(typeof result![i]).toBe('number')
      expect(typeof result![i + 1]).toBe('string')
    }
  })

  it('removes existing layers and sources before adding new ones', async () => {
    mockedExecuteQuery.mockResolvedValue(createFeatureCollection('Polygon', [1, 5]) as any)
    const map = createMockMap()
    map.getLayer.mockReturnValue(true)
    map.getSource.mockReturnValue(true)

    await addGeoJsonLayerAndReturnLegend(map, 'SELECT 1')

    expect(map.removeLayer).toHaveBeenCalledWith('places-area')
    expect(map.removeLayer).toHaveBeenCalledWith('places-points')
    expect(map.removeSource).toHaveBeenCalledWith('places-area-sources')
  })

  it('sets first threshold to 0 when min count is 1', async () => {
    mockedExecuteQuery.mockResolvedValue(createFeatureCollection('Polygon', [1, 50, 100]) as any)
    const map = createMockMap()
    const result = await addGeoJsonLayerAndReturnLegend(map, 'SELECT 1')
    expect(result![0]).toBe(0)
  })
})
