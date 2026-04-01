<script setup lang="ts">
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Protocol } from 'pmtiles'
import { onMounted, watch, watchEffect } from 'vue'
import { storeToRefs } from 'pinia'
import { addGeoJsonLayerAndReturnLegend } from '../services/layer'
import { useAppStore } from '@/store/app.store.ts'
import { executeQuery } from '@/services/duckdb.ts'
import { appConfig } from '@/config'

const dataBase =
  import.meta.env.MODE === 'production'
    ? appConfig.dataBaseUrl
    : 'http://localhost:5173/data'

const parquetFile = `'${dataBase}/anncsu-indirizzi.parquet'`
const pmtilesUrl = `pmtiles://${dataBase}/anncsu-indirizzi.pmtiles`

type Bounds = [[number, number], [number, number]]

async function getBoundsFromPmtiles(): Promise<Bounds> {
  // Read bounds from PMTiles header
  try {
    const { PMTiles } = await import('pmtiles')
    const url = `${dataBase}/anncsu-indirizzi.pmtiles`
    const pm = new PMTiles(url)
    const header = await pm.getHeader()
    return [
      [header.minLon, header.minLat],
      [header.maxLon, header.maxLat],
    ]
  } catch {
    // fallback
  }
  return [[6.63, 35.49], [18.52, 47.09]]
}

async function getBoundsFromParquet(): Promise<Bounds> {
  // Try reading bbox from GeoParquet metadata
  try {
    const metaQuery = `SELECT ST_AsGeoJSON(ST_Point(0,0)) as geometry, value FROM parquet_kv_metadata(${parquetFile}) WHERE key = 'geo'`
    const result = await executeQuery(metaQuery)
    if (result && result.features.length > 0) {
      const geoMeta = JSON.parse((result.features[0].properties as any).value)
      const bbox = geoMeta.columns.geometry.bbox
      return [[bbox[0], bbox[1]], [bbox[2], bbox[3]]]
    }
  } catch {
    // Fall back to computing bounds from data
  }

  // Fallback: compute bounds from coordinates
  try {
    const boundsQuery = `SELECT ST_AsGeoJSON(ST_Point(0,0)) as geometry, MIN(longitude) as min_x, MIN(latitude) as min_y, MAX(longitude) as max_x, MAX(latitude) as max_y FROM read_parquet(${parquetFile})`
    const result = await executeQuery(boundsQuery)
    if (result && result.features.length > 0) {
      const p = result.features[0].properties as any
      return [[p.min_x, p.min_y], [p.max_x, p.max_y]]
    }
  } catch {
    // Should not happen
  }

  // Last resort fallback
  return [[6.63, 35.49], [18.52, 47.09]]
}

async function getBounds(): Promise<Bounds> {
  return appConfig.isNazionale ? getBoundsFromPmtiles() : getBoundsFromParquet()
}

onMounted(async () => {
  // Register PMTiles protocol for nazionale mode
  if (appConfig.isNazionale) {
    const protocol = new Protocol()
    maplibregl.addProtocol('pmtiles', protocol.tile)
  }

  const bounds = await getBounds()

  const map = new maplibregl.Map({
    container: 'map',
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }
      },
      layers: [
        {
          id: 'osm',
          type: 'raster',
          source: 'osm',
          minzoom: 0,
          maxzoom: 19
        }
      ]
    },
    bounds,
    fitBoundsOptions: { padding: 20 },
    bearing: 0,
  })
  map.addControl(new maplibregl.NavigationControl(), 'bottom-right')

  // In nazionale mode, add PMTiles vector source for map visualization
  if (appConfig.isNazionale) {
    map.on('load', () => {
      map.addSource('anncsu-addresses', {
        type: 'vector',
        url: pmtilesUrl,
      })

      map.addLayer({
        id: 'places-points',
        type: 'circle',
        source: 'anncsu-addresses',
        'source-layer': 'addresses',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 2, 12, 5, 18, 10],
          'circle-color': [
            'case',
            ['==', ['get', 'out_of_bounds'], true],
            '#E63946',
            '#4c9b82',
          ],
          'circle-stroke-width': 1,
          'circle-stroke-color': '#ffffff',
        },
      })
    })
  }

  const popup = new maplibregl.Popup({
    closeButton: false,
    closeOnClick: false,
  })

  // Popup for areas (polygons)
  map.on('mousemove', 'places-area', (e) => {
    map.getCanvas().style.cursor = 'pointer'
    const description = `
      <div class="text-lg">
          <div class="font-bold">${e.features[0].properties.name || 'Area'}</div>
          <div>Count: ${e.features[0].properties.count}</div>
      </div>
    `
    popup.setLngLat(e.lngLat).setHTML(description).addTo(map)
  })
  map.on('mouseleave', 'places-area', () => {
    map.getCanvas().style.cursor = ''
    popup.remove()
  })

  // Popup for points
  map.on('mousemove', 'places-points', (e) => {
    map.getCanvas().style.cursor = 'pointer'
    const props = e.features[0].properties
    const address = props.ODONIMO
      ? `${props.ODONIMO}${props.CIVICO ? ' ' + props.CIVICO : ''}${props.ESPONENTE ? ' ' + props.ESPONENTE : ''}`
      : props.name || 'Punto'
    const description = `
      <div class="text-sm">
          <div class="font-bold">${address}</div>
          ${props.NOME_COMUNE ? `<div class="text-gray-600">${props.NOME_COMUNE}</div>` : ''}
          ${props.category ? `<div class="text-gray-600">${props.category}</div>` : ''}
          ${props.out_of_bounds ? `<div class="mt-1 text-xs font-semibold text-red-600">⚠ Fuori confine comunale${props.oob_distance_m ? ` (~${Math.round(Number(props.oob_distance_m))}m)` : ''}</div>` : ''}
      </div>
    `
    popup.setLngLat(e.lngLat).setHTML(description).addTo(map)
  })
  map.on('mouseleave', 'places-points', () => {
    map.getCanvas().style.cursor = ''
    popup.remove()
  })

  const defaultBounds = bounds

  const store = useAppStore()
  const { query, selectedCoordinates, resetView } = storeToRefs(store)

  // In comunale mode, watch for DuckDB query changes to update the map
  if (!appConfig.isNazionale) {
    watchEffect(async () => {
      if (!query.value) return
      const legend = await addGeoJsonLayerAndReturnLegend(map, query.value)
      if (legend) {
        store.setLegend(legend)
      } else {
        store.setQueryError(true)
      }
      store.setQueryLoading(false)
    })
  }

  // Zoom to selected address with highlight
  watch(selectedCoordinates, (coords) => {
    // Remove previous highlight
    if (map.getLayer('selected-address-point')) {
      map.removeLayer('selected-address-point')
    }
    if (map.getSource('selected-address')) {
      map.removeSource('selected-address')
    }

    if (coords) {
      map.flyTo({ center: coords, zoom: 18 })

      // Add highlighted orange point
      map.addSource('selected-address', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [
            {
              type: 'Feature',
              geometry: { type: 'Point', coordinates: coords },
              properties: {},
            },
          ],
        },
      })
      map.addLayer({
        id: 'selected-address-point',
        source: 'selected-address',
        type: 'circle',
        paint: {
          'circle-radius': 12,
          'circle-color': '#FF6B35',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
        },
      })
    }
  })

  // Reset to default view
  watch(resetView, (shouldReset) => {
    if (shouldReset) {
      map.fitBounds(defaultBounds, { padding: 20 })
      store.clearResetView()
    }
  })
})
</script>

<template>
  <div id="map" class="h-full w-full"></div>
</template>

<style scoped></style>
