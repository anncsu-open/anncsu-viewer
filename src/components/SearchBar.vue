<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { useAppStore } from '@/store/app.store.ts'
import { storeToRefs } from 'pinia'
import { anncsuAddressesQuery } from '@/services/queries.ts'
import { executeQuery, executeQueryWithBuffers } from '@/services/duckdb.ts'
import { searchAddresses, SearchCache } from '@/services/search.ts'
import { detectQueryType } from '@/services/smartGeocode.ts'
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
const unifiedInputRef = ref<HTMLInputElement | null>(null)

// Nazionale mode state
const unifiedSearch = ref('')
const comuniList = ref<ComuneEntry[]>([])
const filteredComuni = ref<ComuneEntry[]>([])
const showSuggestions = ref(false)
const selectedComune = ref<ComuneEntry | null>(null)
const suggestionType = ref<'comuni' | 'addresses' | 'combined' | null>(null)

// Combined suggestion state
const combinedSuggestion = ref<{ comune: ComuneEntry; address: string } | null>(null)
const combinedPreview = ref<AddressEntry[]>([])
const combinedTotalCount = ref(0)

// Pre-fetch state: track which comune's tiles are being/have been loaded
const prefetchedComune = ref<string | null>(null)
const prefetchLoading = ref(false)

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

function searchComuni(search: string): ComuneEntry[] {
  if (search.length < 2) return []
  const upper = search.toUpperCase()
  return comuniList.value
    .filter((c) => c.nome.toUpperCase().includes(upper))
    .slice(0, 10)
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

async function loadAddressesForComune(comune: ComuneEntry) {
  store.setQueryLoading(true)

  try {
    // Download H3 tiles for this comune
    const buffers = await loadH3Tiles(comune.h3Cells)
    if (buffers.length === 0) {
      console.error('No H3 tiles found for comune:', comune.nome)
      store.setQueryLoading(false)
      return
    }

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

let prefetchPromise: Promise<void> | null = null

async function prefetchComune(comune: ComuneEntry): Promise<void> {
  // Already loaded for this comune
  if (prefetchedComune.value === comune.codiceIstat && !prefetchLoading.value) return

  // Already loading for this comune — return existing promise
  if (prefetchLoading.value && prefetchedComune.value === comune.codiceIstat && prefetchPromise) {
    return prefetchPromise
  }

  prefetchLoading.value = true
  prefetchedComune.value = comune.codiceIstat
  searchCache.clear()

  prefetchPromise = loadAddressesForComune(comune).finally(() => {
    prefetchLoading.value = false
  })

  return prefetchPromise
}

async function selectComune(comune: ComuneEntry) {
  cancelBlur()
  selectedComune.value = comune
  unifiedSearch.value = ''
  showSuggestions.value = false
  searchCache.clear()

  // Wait for prefetch if in progress, otherwise load fresh
  if (prefetchLoading.value && prefetchedComune.value === comune.codiceIstat && prefetchPromise) {
    await prefetchPromise
  } else if (prefetchedComune.value !== comune.codiceIstat || addressList.value.length === 0) {
    await loadAddressesForComune(comune)
    prefetchedComune.value = comune.codiceIstat
  }

  // Restore focus on input
  nextTick(() => unifiedInputRef.value?.focus())
}

async function selectCombined(comune: ComuneEntry, address: string) {
  cancelBlur()
  selectedComune.value = comune
  showSuggestions.value = false

  // Use prefetched data if available
  if (prefetchedComune.value !== comune.codiceIstat) {
    searchCache.clear()
    await loadAddressesForComune(comune)
    prefetchedComune.value = comune.codiceIstat
  }

  // Set the address part and search
  unifiedSearch.value = address

  const results = searchAddresses(addressList.value, address, 10)
  searchCache.set(address, results)

  if (results.length > 0) {
    filteredAddresses.value = results
    suggestionType.value = 'addresses'
    showSuggestions.value = true
  }

  // Restore focus on input
  nextTick(() => unifiedInputRef.value?.focus())
}

function clearComune() {
  selectedComune.value = null
  unifiedSearch.value = ''
  addressList.value = []
  filteredAddresses.value = []
  showSuggestions.value = false
  searchCache.clear()
  onClear()
}

function clearAll() {
  if (selectedComune.value) {
    // Clear only address search, keep comune
    unifiedSearch.value = ''
    filteredAddresses.value = []
    showSuggestions.value = false
    store.setSelectedCoordinates(null)
    store.triggerResetView()
  } else {
    clearComune()
  }
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

let blurTimeout: number | null = null

function onBlur() {
  blurTimeout = window.setTimeout(() => {
    showSuggestions.value = false
    showAutocomplete.value = false
    blurTimeout = null
  }, 200)
}

function cancelBlur() {
  if (blurTimeout !== null) {
    window.clearTimeout(blurTimeout)
    blurTimeout = null
  }
}

// Unified search watcher (nazionale mode)
watch(unifiedSearch, (newValue) => {
  if (!appConfig.isNazionale) return

  if (newValue.length < 2) {
    showSuggestions.value = false
    filteredComuni.value = []
    filteredAddresses.value = []
    combinedSuggestion.value = null
    suggestionType.value = null
    return
  }

  if (selectedComune.value) {
    // Comune already selected — search addresses
    const cached = searchCache.get(newValue)
    let results: AddressEntry[]
    if (cached) {
      results = cached
    } else {
      results = searchAddresses(addressList.value, newValue, 10)
      searchCache.set(newValue, results)
    }

    filteredAddresses.value = results
    suggestionType.value = 'addresses'
    showSuggestions.value = filteredAddresses.value.length > 0
    return
  }

  // No comune selected — detect query type
  const comuniInfo = comuniList.value.map((c) => ({ nome: c.nome, codiceIstat: c.codiceIstat }))
  const detection = detectQueryType(newValue, comuniInfo)

  if (detection.type === 'combined' && detection.comune) {
    const fullComune = comuniList.value.find((c) => c.codiceIstat === detection.comune!.codiceIstat)
    if (fullComune) {
      const addr = detection.address || ''
      combinedSuggestion.value = { comune: fullComune, address: addr }
      suggestionType.value = 'combined'
      showSuggestions.value = true

      // Build preview: use already-loaded data or wait for prefetch
      const tilesReady = prefetchedComune.value === fullComune.codiceIstat && !prefetchLoading.value && addressList.value.length > 0

      if (tilesReady) {
        // Tiles already loaded — build preview immediately
        if (addr.length >= 2) {
          const results = searchAddresses(addressList.value, addr, 10)
          combinedPreview.value = results.slice(0, 4)
          combinedTotalCount.value = results.length
        } else {
          combinedPreview.value = []
          combinedTotalCount.value = addressList.value.length
        }
      } else {
        // Tiles not ready — start prefetch, show preview when done
        combinedPreview.value = []
        combinedTotalCount.value = 0
        prefetchComune(fullComune).then(() => {
          if (combinedSuggestion.value?.comune.codiceIstat === fullComune.codiceIstat) {
            const currentAddr = combinedSuggestion.value.address
            if (currentAddr && currentAddr.length >= 2) {
              const results = searchAddresses(addressList.value, currentAddr, 10)
              combinedPreview.value = results.slice(0, 4)
              combinedTotalCount.value = results.length
            } else {
              combinedPreview.value = []
              combinedTotalCount.value = addressList.value.length
            }
          }
        })
      }
      return
    }
  }

  // Check for trailing comma: "Vacone," — pre-fetch tiles
  const commaTrailing = newValue.match(/^(.+?)\s*,\s*$/)
  if (commaTrailing) {
    const comunePart = commaTrailing[1].trim()
    const comuneInfo = comuniList.value.find((c) => c.nome.toUpperCase() === comunePart.toUpperCase())
    if (comuneInfo) {
      prefetchComune(comuneInfo)
    }
  }

  // Default: search comuni (strip trailing comma for search)
  const searchText = newValue.replace(/,\s*$/, '').trim()
  filteredComuni.value = searchComuni(searchText)
  combinedSuggestion.value = null
  combinedPreview.value = []
  combinedTotalCount.value = 0
  suggestionType.value = 'comuni'
  showSuggestions.value = filteredComuni.value.length > 0
})

// Filter addresses with multi-term matching + Jaccard similarity ranking (LRU cached)
watch(searchFilter, (newValue) => {
  if (appConfig.isNazionale) return // Handled by unifiedSearch watcher

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
  if (appConfig.isNazionale) {
    unifiedSearch.value = entry.name
    showSuggestions.value = false
  } else {
    store.setSearchFilter(entry.name)
    showAutocomplete.value = false
  }
  store.setSelectedCoordinates(entry.coordinates)
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
      <!-- Nazionale mode: unified search -->
      <template v-if="appConfig.isNazionale">
        <label class="mb-1 text-xs font-semibold uppercase tracking-wide text-[#0066CC]">
          Cerca comune e indirizzo
        </label>

        <!-- Comune chip -->
        <div
          v-if="selectedComune"
          data-testid="comune-chip"
          class="mb-1 flex items-center gap-1 rounded-full bg-[#0066CC]/10 px-3 py-1 text-sm text-[#0066CC]"
        >
          <svg class="h-4 w-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4zm3 1h2v2H7V5zm2 4H7v2h2V9zm2-4h2v2h-2V5zm2 4h-2v2h2V9z" clip-rule="evenodd" />
          </svg>
          <span class="font-semibold">{{ selectedComune.nome }}</span>
          <button
            data-testid="comune-chip-close"
            @click="clearComune"
            class="ml-1 rounded-full p-0.5 transition-colors hover:bg-[#0066CC]/20"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="h-3.5 w-3.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

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
            ref="unifiedInputRef"
            data-testid="unified-search-input"
            type="text"
            v-model="unifiedSearch"
            @focus="showSuggestions = (filteredComuni.length > 0 || filteredAddresses.length > 0 || combinedSuggestion !== null)"
            @blur="onBlur"
            :placeholder="selectedComune ? 'es. VIA ROMA 15' : 'es. Vacone o Vacone Via Roma 15'"
            class="w-full border-b-2 border-gray-300 bg-gray-50 py-3 pl-10 pr-10 text-sm font-titillium transition-colors placeholder:text-gray-400 focus:border-[#0066CC] focus:bg-white focus:outline-none"
          />
          <button
            v-if="unifiedSearch || selectedComune"
            data-testid="clear-search"
            @click="clearAll"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-[#0066CC]"
            title="Clear search"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="h-5 w-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <!-- Suggestions dropdown -->
          <div
            v-if="showSuggestions"
            class="absolute top-full z-10 mt-1 max-h-60 w-full overflow-y-auto rounded bg-white shadow-lg ring-1 ring-gray-200"
          >
            <!-- Combined suggestion with address preview -->
            <div
              v-if="suggestionType === 'combined' && combinedSuggestion"
              data-testid="combined-suggestion"
              @click="selectCombined(combinedSuggestion.comune, combinedSuggestion.address)"
              class="cursor-pointer border-b border-gray-100 px-4 py-3 text-sm transition-colors hover:bg-[#0066CC]/10"
            >
              <div class="flex items-center gap-2">
                <svg class="h-4 w-4 flex-shrink-0 text-[#0066CC]" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4zm3 1h2v2H7V5zm2 4H7v2h2V9zm2-4h2v2h-2V5zm2 4h-2v2h2V9z" clip-rule="evenodd" />
                </svg>
                <span class="font-semibold text-[#0066CC]">{{ combinedSuggestion.comune.nome }}</span>
                <span class="text-gray-400">→</span>
                <span>{{ combinedSuggestion.address }}</span>
                <span v-if="prefetchLoading" class="ml-auto text-xs text-gray-400">caricamento...</span>
              </div>
              <!-- Address previews -->
              <div v-if="combinedPreview.length > 0" class="ml-6 mt-1.5 space-y-0.5">
                <div
                  v-for="(entry, index) in combinedPreview"
                  :key="index"
                  data-testid="address-preview"
                  class="flex items-center gap-1.5 text-xs text-gray-500"
                >
                  <svg class="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
                  </svg>
                  {{ entry.name }}
                </div>
                <div
                  v-if="combinedTotalCount > combinedPreview.length"
                  data-testid="more-results"
                  class="ml-4.5 text-xs italic text-gray-400"
                >
                  ... e altri {{ combinedTotalCount - combinedPreview.length }} risultati
                </div>
              </div>
            </div>

            <!-- Comune suggestions -->
            <template v-if="suggestionType === 'comuni'">
              <div
                v-for="(comune, index) in filteredComuni"
                :key="index"
                data-testid="comune-suggestion"
                @click="selectComune(comune)"
                class="flex cursor-pointer items-center gap-2 border-b border-gray-100 px-4 py-3 text-sm transition-colors last:border-b-0 hover:bg-[#0066CC]/10 hover:text-[#0066CC]"
              >
                <svg class="h-4 w-4 flex-shrink-0 text-[#0066CC]" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4zm3 1h2v2H7V5zm2 4H7v2h2V9zm2-4h2v2h-2V5zm2 4h-2v2h2V9z" clip-rule="evenodd" />
                </svg>
                {{ comune.nome }}
              </div>
            </template>

            <!-- Address suggestions -->
            <template v-if="suggestionType === 'addresses'">
              <div
                v-for="(entry, index) in filteredAddresses"
                :key="index"
                data-testid="address-suggestion"
                @click="selectAddress(entry)"
                class="flex cursor-pointer items-center gap-2 border-b border-gray-100 px-4 py-3 text-sm transition-colors last:border-b-0 hover:bg-[#0066CC]/10 hover:text-[#0066CC]"
              >
                <svg class="h-4 w-4 flex-shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
                </svg>
                {{ entry.name }}
              </div>
            </template>
          </div>
        </div>
      </template>

      <!-- Comunale mode: address search only -->
      <template v-else>
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
            @focus="showAutocomplete = filteredAddresses.length > 0"
            @blur="onBlur"
            placeholder="es. VIA ROMA 15"
            class="w-full border-b-2 border-gray-300 bg-gray-50 py-3 pl-10 pr-10 text-sm font-titillium transition-colors placeholder:text-gray-400 focus:border-[#0066CC] focus:bg-white focus:outline-none"
          />
          <button
            v-if="searchFilter"
            @click="onClear"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-[#0066CC]"
            title="Clear search"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="h-5 w-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <!-- Address autocomplete (comunale mode) -->
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
      </template>
    </div>
  </div>
</template>
