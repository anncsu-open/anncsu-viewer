<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useAppStore } from '@/store/app.store.ts'
import { storeToRefs } from 'pinia'
import { anncsuAddressesQuery } from '@/services/queries.ts'
import { executeQuery, executeQueryWithBuffers } from '@/services/duckdb.ts'
import { searchAddresses, SearchCache } from '@/services/search.ts'
import { appConfig } from '@/config'
import type { Feature, Point } from 'geojson'

const store = useAppStore()
const { searchFilter } = storeToRefs(store)

const dataBase =
  import.meta.env.MODE === 'production'
    ? appConfig.dataBaseUrl
    : 'http://localhost:5173/data'

const addressesParquet = `read_parquet('${dataBase}/anncsu-indirizzi.parquet')`

interface AddressEntry {
  name: string
  coordinates: [number, number]
}

interface ComuneEntry {
  nome: string
  codiceIstat: string
  h3Cells: string[]
}

const addressList = ref<AddressEntry[]>([])
const filteredAddresses = ref<AddressEntry[]>([])
const showAutocomplete = ref(false)
const searchCache = new SearchCache<AddressEntry[]>()

// Nazionale mode state
const comuneSearch = ref('')
const comuniList = ref<ComuneEntry[]>([])
const filteredComuni = ref<ComuneEntry[]>([])
const showComuneAutocomplete = ref(false)
const selectedComune = ref<ComuneEntry | null>(null)

function transformQuery(filter?: string, codiceIstat?: string): string {
  if (filter) {
    const parts = filter.trim().split(/\s+/)
    const civico = parts[parts.length - 1]
    const odonimo = parts.slice(0, -1).join(' ').toUpperCase()

    let whereClause = `UPPER(ODONIMO) = '${odonimo}' AND CAST(CIVICO AS VARCHAR) = '${civico}'`
    if (codiceIstat) {
      whereClause += ` AND CODICE_ISTAT = '${codiceIstat}'`
    }

    return anncsuAddressesQuery.replace(
      'FROM addresses',
      `FROM (SELECT * FROM ${addressesParquet} WHERE ${whereClause}) as addresses`,
    )
  }

  if (codiceIstat) {
    return anncsuAddressesQuery.replace(
      'FROM addresses',
      `FROM (SELECT * FROM ${addressesParquet} WHERE CODICE_ISTAT = '${codiceIstat}') as addresses`,
    )
  }

  return anncsuAddressesQuery.replace('FROM addresses', `FROM ${addressesParquet} as addresses`)
}

async function loadComuni() {
  try {
    const response = await fetch(`${dataBase}/comuni-h3.json`)
    const data: { codice_istat: string; nome_comune: string; h3_cells: string[] }[] = await response.json()
    comuniList.value = data.map((d) => ({
      nome: d.nome_comune,
      codiceIstat: d.codice_istat,
      h3Cells: d.h3_cells,
    }))
  } catch (error) {
    console.error('Error loading comuni:', error)
  }
}

function searchComuni(search: string) {
  if (search.length < 2) {
    filteredComuni.value = []
    showComuneAutocomplete.value = false
    return
  }

  const upper = search.toUpperCase()
  filteredComuni.value = comuniList.value
    .filter((c) => c.nome.toUpperCase().includes(upper))
    .slice(0, 10)
  showComuneAutocomplete.value = filteredComuni.value.length > 0
}

async function loadH3Tiles(h3Cells: string[]): Promise<ArrayBuffer[]> {
  const buffers: ArrayBuffer[] = []
  for (const cell of h3Cells) {
    try {
      const url = `${dataBase}/tiles/h3_cell=${cell}/${cell}.parquet`
      const response = await fetch(url)
      if (response.ok) {
        buffers.push(await response.arrayBuffer())
      }
    } catch {
      // Skip missing tiles
    }
  }
  return buffers
}

async function selectComune(comune: ComuneEntry) {
  selectedComune.value = comune
  comuneSearch.value = comune.nome
  showComuneAutocomplete.value = false
  store.setQueryLoading(true)

  try {
    // Download H3 tiles for this comune
    const buffers = await loadH3Tiles(comune.h3Cells)
    if (buffers.length === 0) {
      console.error('No H3 tiles found for comune:', comune.nome)
      store.setQueryLoading(false)
      return
    }

    // Build a query that reads from all tile buffers registered in DuckDB
    // We use executeQueryWithBuffers which registers the buffers first
    const tileNames = comune.h3Cells.map((_, i) => `tile_${i}.parquet`)
    const unionQuery = tileNames.map((name) => `SELECT * FROM read_parquet('${name}')`).join(' UNION ALL ')

    const loadQuery = anncsuAddressesQuery.replace(
      'FROM addresses',
      `FROM (${unionQuery}) as addresses WHERE CODICE_ISTAT = '${comune.codiceIstat}'`,
    )

    const data = await executeQueryWithBuffers(loadQuery, buffers, tileNames)
    if (data) {
      const seen = new Set<string>()
      addressList.value = data.features
        .map((f: Feature) => {
          const name = (f.properties as any).name as string
          const coordinates = (f.geometry as Point).coordinates as [number, number]
          return { name, coordinates }
        })
        .filter((entry) => {
          if (!entry.name || seen.has(entry.name)) return false
          seen.add(entry.name)
          return true
        })
        .sort((a, b) => a.name.localeCompare(b.name))
    }
  } catch (error) {
    console.error('Error loading addresses for comune:', error)
  }

  store.setQueryLoading(false)
}

function clearComune() {
  selectedComune.value = null
  comuneSearch.value = ''
  addressList.value = []
  filteredAddresses.value = []
  showComuneAutocomplete.value = false
  searchCache.clear()
  onClear()
}

onMounted(async () => {
  if (appConfig.isNazionale) {
    await loadComuni()
    store.setQueryLoading(false)
    return
  }

  // Comunale mode: load all addresses for autocomplete
  store.setQueryLoading(true)
  store.setQuery(transformQuery())

  try {
    const loadQuery = anncsuAddressesQuery.replace(
      'FROM addresses',
      `FROM ${addressesParquet} as addresses`,
    )
    const data = await executeQuery(loadQuery)
    if (data) {
      const seen = new Set<string>()
      addressList.value = data.features
        .map((f: Feature) => {
          const name = (f.properties as any).name as string
          const coordinates = (f.geometry as Point).coordinates as [number, number]
          return { name, coordinates }
        })
        .filter((entry) => {
          if (!entry.name || seen.has(entry.name)) return false
          seen.add(entry.name)
          return true
        })
        .sort((a, b) => a.name.localeCompare(b.name))
    }
  } catch (error) {
    console.error('Error loading addresses:', error)
  }
})

function onComuneBlur() {
  window.setTimeout(() => (showComuneAutocomplete.value = false), 200)
}

function onAddressBlur() {
  window.setTimeout(() => (showAutocomplete.value = false), 200)
}

// Watch comune search input (nazionale mode)
watch(comuneSearch, (newValue) => {
  if (selectedComune.value && newValue !== selectedComune.value.nome) {
    selectedComune.value = null
    addressList.value = []
    filteredAddresses.value = []
  }
  searchComuni(newValue)
})

// Filter addresses with multi-term matching + Jaccard similarity ranking (LRU cached)
watch(searchFilter, (newValue) => {
  if (newValue.length >= 2) {
    const cached = searchCache.get(newValue)
    if (cached) {
      filteredAddresses.value = cached
    } else {
      const results = searchAddresses(addressList.value, newValue, 10)
      searchCache.set(newValue, results)
      filteredAddresses.value = results
    }
    showAutocomplete.value = filteredAddresses.value.length > 0
  } else {
    showAutocomplete.value = false
    filteredAddresses.value = []
  }
})

function selectAddress(entry: AddressEntry) {
  store.setSearchFilter(entry.name)
  store.setSelectedCoordinates(entry.coordinates)
  showAutocomplete.value = false
  store.setQueryLoading(true)
  store.setQuery(transformQuery(entry.name, selectedComune.value?.codiceIstat))
}

function onClear() {
  store.setSearchFilter('')
  store.setSelectedCoordinates(null)
  store.triggerResetView()
  if (!appConfig.isNazionale) {
    store.setQueryLoading(true)
    store.setQuery(transformQuery())
  }
}
</script>

<template>
  <div class="absolute left-1/2 top-4 z-20 w-[28rem] -translate-x-1/2 transform">
    <div class="relative flex flex-col gap-1 rounded bg-white p-4 shadow-lg ring-1 ring-gray-200">
      <!-- Comune selector (nazionale mode only) -->
      <template v-if="appConfig.isNazionale">
        <label class="mb-1 text-xs font-semibold uppercase tracking-wide text-[#0066CC]">
          Seleziona comune
        </label>
        <div class="relative mb-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="2"
            stroke="currentColor"
            class="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21" />
          </svg>
          <input
            data-testid="comune-input"
            type="text"
            v-model="comuneSearch"
            @focus="showComuneAutocomplete = filteredComuni.length > 0"
            @blur="onComuneBlur"
            placeholder="es. Vacone"
            class="w-full border-b-2 border-gray-300 bg-gray-50 py-3 pl-10 pr-10 text-sm font-titillium transition-colors placeholder:text-gray-400 focus:border-[#0066CC] focus:bg-white focus:outline-none"
          />
          <button
            v-if="comuneSearch"
            @click="clearComune"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-[#0066CC]"
            title="Cancella comune"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="h-5 w-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <!-- Comune autocomplete -->
          <div
            v-if="showComuneAutocomplete && filteredComuni.length > 0"
            class="absolute top-full z-10 mt-1 max-h-60 w-full overflow-y-auto rounded bg-white shadow-lg ring-1 ring-gray-200"
          >
            <div
              v-for="(comune, index) in filteredComuni"
              :key="index"
              data-testid="comune-suggestion"
              @click="selectComune(comune)"
              class="cursor-pointer border-b border-gray-100 px-4 py-3 text-sm transition-colors last:border-b-0 hover:bg-[#0066CC]/10 hover:text-[#0066CC]"
            >
              {{ comune.nome }}
            </div>
          </div>
        </div>
      </template>

      <!-- Address search -->
      <label for="search-address" class="mb-1 text-xs font-semibold uppercase tracking-wide text-[#0066CC]">
        Cerca indirizzo
      </label>
      <div class="relative">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="2"
          stroke="currentColor"
          class="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
        <input
          id="search-address"
          data-testid="address-input"
          type="text"
          v-model="searchFilter"
          :disabled="appConfig.isNazionale && !selectedComune"
          @focus="showAutocomplete = filteredAddresses.length > 0"
          @blur="onAddressBlur"
          :placeholder="appConfig.isNazionale && !selectedComune ? 'Prima seleziona un comune' : 'es. VIA ROMA 15'"
          class="w-full border-b-2 border-gray-300 bg-gray-50 py-3 pl-10 pr-10 text-sm font-titillium transition-colors placeholder:text-gray-400 focus:border-[#0066CC] focus:bg-white focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        />
        <button
          v-if="searchFilter"
          @click="onClear"
          class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-[#0066CC]"
          title="Cancella ricerca"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="h-5 w-5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <!-- Address autocomplete -->
      <div
        v-if="showAutocomplete && filteredAddresses.length > 0"
        class="absolute top-full z-10 mt-1 max-h-60 w-full overflow-y-auto rounded bg-white shadow-lg ring-1 ring-gray-200"
      >
        <div
          v-for="(entry, index) in filteredAddresses"
          :key="index"
          @click="selectAddress(entry)"
          class="cursor-pointer border-b border-gray-100 px-4 py-3 text-sm transition-colors last:border-b-0 hover:bg-[#0066CC]/10 hover:text-[#0066CC]"
        >
          {{ entry.name }}
        </div>
      </div>
    </div>
  </div>
</template>
