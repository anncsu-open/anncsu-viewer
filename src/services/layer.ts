import { Map } from 'maplibre-gl'
import { executeQuery } from './duckdb'
import type { Feature } from 'geojson'

export const colors = ['#d3f2a3', '#97e196', '#6cc08b', '#4c9b82', '#217a79', '#105965', '#074050']

export async function addGeoJsonLayerAndReturnLegend(map: Map, query = '') {
  const data = await executeQuery(query)

  if (!data) return

  console.log('Data returned:', data)

  const counts = data.features.map((f: Feature) => f.properties.count)
  const max = Math.max(...counts)
  const min = Math.min(...counts)
  const nbClasses = colors.length

  const logMin = Math.log10(Math.max(min, 1))
  const logMax = Math.log10(max)
  const interval = (logMax - logMin) / nbClasses

  const colorGradient = colors
    .map((color, i) => [Math.pow(10, logMin + interval * i), color])
    .flat()
  if (colorGradient[0] === 1) {
    colorGradient[0] = 0
  }

  // Remove existing layers
  if (map.getLayer('places-area')) {
    map.removeLayer('places-area')
  }
  if (map.getLayer('places-points')) {
    map.removeLayer('places-points')
  }
  if (map.getSource('places-area-sources')) {
    map.removeSource('places-area-sources')
  }

  // Add source
  map.addSource('places-area-sources', {
    type: 'geojson',
    data,
  })

  // Determine geometry type
  const firstGeometry = data.features[0]?.geometry?.type

  if (firstGeometry === 'Point') {
    // Layer for points (places of interest)
    map.addLayer({
      id: 'places-points',
      type: 'circle',
      source: 'places-area-sources',
      paint: {
        'circle-radius': 6,
        'circle-color': '#4c9b82',
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffffff',
      },
    })
  } else {
    // Layer for polygons (H3 grid or areas)
    map.addLayer({
      id: 'places-area',
      type: 'fill',
      source: 'places-area-sources',
      paint: {
        'fill-color': ['interpolate', ['linear'], ['get', 'count'], ...colorGradient],
        'fill-outline-color': 'grey',
        'fill-opacity': 0.8,
      },
    })
  }

  return colorGradient
}
