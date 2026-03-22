interface CacheEntry<T> {
  value: T
  timestamp: number
}

/**
 * LRU cache with TTL expiration.
 * Keys are normalized (lowercased, trimmed) for consistent lookups.
 */
export class SearchCache<T> {
  private cache = new Map<string, CacheEntry<T>>()
  private maxSize: number
  private ttlMs: number

  constructor({ maxSize = 100, ttlMs = 5 * 60 * 1000 }: { maxSize?: number; ttlMs?: number } = {}) {
    this.maxSize = maxSize
    this.ttlMs = ttlMs
  }

  private normalizeKey(key: string): string {
    return key.toLowerCase().trim()
  }

  get(key: string): T | undefined {
    const k = this.normalizeKey(key)
    const entry = this.cache.get(k)
    if (!entry) return undefined

    if (Date.now() - entry.timestamp > this.ttlMs) {
      this.cache.delete(k)
      return undefined
    }

    // Refresh position (LRU): delete and re-insert to move to end
    this.cache.delete(k)
    this.cache.set(k, entry)

    return entry.value
  }

  set(key: string, value: T): void {
    const k = this.normalizeKey(key)

    // Delete first if exists (to refresh position)
    this.cache.delete(k)

    // Evict oldest if at capacity
    if (this.cache.size >= this.maxSize) {
      const oldestKey = this.cache.keys().next().value
      if (oldestKey) this.cache.delete(oldestKey)
    }

    this.cache.set(k, { value, timestamp: Date.now() })
  }

  clear(): void {
    this.cache.clear()
  }
}

interface AddressEntry {
  name: string
  coordinates: [number, number]
}

/**
 * Compute bigrams (2-character substrings) of a string.
 */
function bigrams(str: string): Set<string> {
  const s = str.toUpperCase()
  const result = new Set<string>()
  for (let i = 0; i < s.length - 1; i++) {
    result.add(s.slice(i, i + 2))
  }
  return result
}

/**
 * Jaccard similarity between two strings based on bigrams.
 * Returns a value between 0.0 (no similarity) and 1.0 (identical).
 */
export function jaccardSimilarity(a: string, b: string): number {
  const bigramsA = bigrams(a)
  const bigramsB = bigrams(b)

  if (bigramsA.size === 0 && bigramsB.size === 0) return 0.0

  let intersection = 0
  for (const bg of bigramsA) {
    if (bigramsB.has(bg)) intersection++
  }

  const union = bigramsA.size + bigramsB.size - intersection
  if (union === 0) return 0.0

  return intersection / union
}

/**
 * Search addresses using multi-term CONTAINS filtering and Jaccard similarity ranking.
 *
 * - Splits query into terms (min 2 chars each)
 * - Filters addresses that contain ALL terms (order-independent)
 * - Ranks results by Jaccard similarity to the full query
 * - Returns up to maxResults entries
 */
export function searchAddresses(
  addresses: AddressEntry[],
  query: string,
  maxResults: number = 10,
): AddressEntry[] {
  const trimmed = query.trim()
  if (trimmed.length < 2) return []

  const upperQuery = trimmed.toUpperCase()
  const terms = upperQuery.split(/\s+/).filter((t) => t.length >= 2)

  if (terms.length === 0) return []

  // Filter: address must contain all terms
  const filtered = addresses.filter((entry) => {
    const upper = entry.name.toUpperCase()
    return terms.every((term) => upper.includes(term))
  })

  // Rank by Jaccard similarity
  const scored = filtered.map((entry) => ({
    entry,
    similarity: jaccardSimilarity(upperQuery, entry.name),
  }))

  scored.sort((a, b) => b.similarity - a.similarity)

  return scored.slice(0, maxResults).map((s) => s.entry)
}
