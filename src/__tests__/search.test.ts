import { describe, it, expect, vi, beforeEach } from 'vitest'
import { searchAddresses, jaccardSimilarity, SearchCache } from '@/services/search'

const addresses = [
  { name: 'VIA ROMA 1', coordinates: [12.5, 42.0] as [number, number] },
  { name: 'VIA ROMA 15', coordinates: [12.5, 42.1] as [number, number] },
  { name: 'VIA ROMA 2', coordinates: [12.5, 42.2] as [number, number] },
  { name: 'PIAZZA GARIBALDI 3', coordinates: [12.6, 42.0] as [number, number] },
  { name: 'VIA GARIBALDI 10', coordinates: [12.6, 42.1] as [number, number] },
  { name: 'VIA GIUSEPPE VERDI 5', coordinates: [12.7, 42.0] as [number, number] },
  { name: 'VICOLO STRETTO 1', coordinates: [12.8, 42.0] as [number, number] },
  { name: 'VIA VITTORIO EMANUELE 22', coordinates: [12.9, 42.0] as [number, number] },
]

describe('jaccardSimilarity', () => {
  it('returns 1.0 for identical strings', () => {
    expect(jaccardSimilarity('VIA ROMA', 'VIA ROMA')).toBe(1.0)
  })

  it('returns 0.0 for completely different strings', () => {
    expect(jaccardSimilarity('ABC', 'XYZ')).toBe(0.0)
  })

  it('returns a value between 0 and 1 for partially similar strings', () => {
    const sim = jaccardSimilarity('VIA ROMA', 'VIA ROMAGNA')
    expect(sim).toBeGreaterThan(0)
    expect(sim).toBeLessThan(1)
  })

  it('is case insensitive', () => {
    expect(jaccardSimilarity('via roma', 'VIA ROMA')).toBe(1.0)
  })

  it('returns 0.0 for empty strings', () => {
    expect(jaccardSimilarity('', '')).toBe(0.0)
  })
})

describe('searchAddresses', () => {
  it('returns results matching a single term', () => {
    const results = searchAddresses(addresses, 'ROMA')
    expect(results.length).toBeGreaterThan(0)
    expect(results.every((r) => r.name.includes('ROMA'))).toBe(true)
  })

  it('returns results matching multiple terms', () => {
    const results = searchAddresses(addresses, 'VIA GARIBALDI')
    expect(results.some((r) => r.name === 'VIA GARIBALDI 10')).toBe(true)
  })

  it('ranks exact matches higher than partial matches', () => {
    const results = searchAddresses(addresses, 'VIA ROMA 1')
    expect(results[0].name).toBe('VIA ROMA 1')
  })

  it('limits results to maxResults', () => {
    const results = searchAddresses(addresses, 'VIA', 3)
    expect(results.length).toBeLessThanOrEqual(3)
  })

  it('returns empty array for empty query', () => {
    const results = searchAddresses(addresses, '')
    expect(results).toEqual([])
  })

  it('returns empty array for query shorter than 2 characters', () => {
    const results = searchAddresses(addresses, 'V')
    expect(results).toEqual([])
  })

  it('matches partial terms (fuzzy)', () => {
    // "ROM" should match "ROMA"
    const results = searchAddresses(addresses, 'ROM')
    expect(results.length).toBeGreaterThan(0)
    expect(results.some((r) => r.name.includes('ROMA'))).toBe(true)
  })

  it('matches with terms in different order', () => {
    // "GARIBALDI VIA" should match "VIA GARIBALDI 10"
    const results = searchAddresses(addresses, 'GARIBALDI VIA')
    expect(results.some((r) => r.name === 'VIA GARIBALDI 10')).toBe(true)
  })

  it('handles civic number in search', () => {
    const results = searchAddresses(addresses, 'VIA ROMA 15')
    expect(results[0].name).toBe('VIA ROMA 15')
  })

  it('results are sorted by similarity descending', () => {
    const results = searchAddresses(addresses, 'VIA ROMA')
    // All VIA ROMA entries should come before others
    const romaResults = results.filter((r) => r.name.startsWith('VIA ROMA'))
    const otherResults = results.filter((r) => !r.name.startsWith('VIA ROMA'))
    if (romaResults.length > 0 && otherResults.length > 0) {
      const lastRomaIndex = results.indexOf(romaResults[romaResults.length - 1])
      const firstOtherIndex = results.indexOf(otherResults[0])
      expect(lastRomaIndex).toBeLessThan(firstOtherIndex)
    }
  })
})

describe('SearchCache', () => {
  let cache: SearchCache<string[]>

  beforeEach(() => {
    cache = new SearchCache({ maxSize: 3, ttlMs: 5 * 60 * 1000 })
  })

  it('stores and retrieves a cached value', () => {
    cache.set('key1', ['a', 'b'])
    expect(cache.get('key1')).toEqual(['a', 'b'])
  })

  it('returns undefined for missing keys', () => {
    expect(cache.get('nonexistent')).toBeUndefined()
  })

  it('evicts oldest entry when maxSize is exceeded', () => {
    cache.set('key1', ['a'])
    cache.set('key2', ['b'])
    cache.set('key3', ['c'])
    cache.set('key4', ['d']) // should evict key1

    expect(cache.get('key1')).toBeUndefined()
    expect(cache.get('key2')).toEqual(['b'])
    expect(cache.get('key4')).toEqual(['d'])
  })

  it('returns undefined for expired entries', () => {
    const shortTtlCache = new SearchCache<string[]>({ maxSize: 10, ttlMs: 50 })
    shortTtlCache.set('key1', ['a'])

    vi.useFakeTimers()
    vi.advanceTimersByTime(100)

    expect(shortTtlCache.get('key1')).toBeUndefined()

    vi.useRealTimers()
  })

  it('refreshes position on get (LRU behavior)', () => {
    cache.set('key1', ['a'])
    cache.set('key2', ['b'])
    cache.set('key3', ['c'])

    // Access key1 to make it most recently used
    cache.get('key1')

    // Add key4 — should evict key2 (oldest unused), not key1
    cache.set('key4', ['d'])

    expect(cache.get('key1')).toEqual(['a'])
    expect(cache.get('key2')).toBeUndefined()
    expect(cache.get('key3')).toEqual(['c'])
    expect(cache.get('key4')).toEqual(['d'])
  })

  it('clear removes all entries', () => {
    cache.set('key1', ['a'])
    cache.set('key2', ['b'])
    cache.clear()

    expect(cache.get('key1')).toBeUndefined()
    expect(cache.get('key2')).toBeUndefined()
  })

  it('normalizes keys (case insensitive, trimmed)', () => {
    cache.set('  Via Roma  ', ['a'])
    expect(cache.get('via roma')).toEqual(['a'])
  })
})
