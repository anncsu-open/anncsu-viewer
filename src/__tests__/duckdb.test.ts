import { describe, it, expect, vi, beforeEach } from 'vitest'

const { queries, selectBundle } = vi.hoisted(() => ({
  queries: [] as string[],
  selectBundle: vi.fn(
    async (bundles: Record<string, { mainModule: string; mainWorker: string }>) => ({
      mainModule: bundles.base.mainModule,
      mainWorker: bundles.base.mainWorker,
      pthreadWorker: null,
    }),
  ),
}))

vi.mock('@duckdb/duckdb-wasm', () => {
  class AsyncDuckDB {
    instantiate = vi.fn()
    registerFileURL = vi.fn()
    registerFileBuffer = vi.fn()
    terminate = vi.fn()
    async connect() {
      return {
        query: vi.fn(async (sql: string) => {
          queries.push(sql)
          return { toArray: () => [] }
        }),
        close: vi.fn(),
      }
    }
  }
  return {
    AsyncDuckDB,
    ConsoleLogger: class {},
    DuckDBDataProtocol: { HTTP: 4 },
    selectBundle,
  }
})

import { executeQuery, executeQueryWithBuffers } from '@/services/duckdb'

describe('duckdb service', () => {
  beforeEach(() => {
    queries.length = 0
    selectBundle.mockClear()
    vi.stubGlobal(
      'Worker',
      class {
        terminate() {}
      },
    )
  })

  it('offers only the DuckDB 2 base bundle, which runs without cross-origin isolation', async () => {
    await executeQuery('SELECT 1')
    const bundles = selectBundle.mock.calls[0][0]
    expect(Object.keys(bundles)).toEqual(['base'])
    expect(bundles.base.mainModule).toMatch(/duckdb-base.*\.wasm/)
    expect(bundles.base.mainWorker).toMatch(/duckdb-browser-base\.worker/)
  })

  const runs: [string, () => Promise<unknown>][] = [
    ['executeQuery', () => executeQuery('SELECT 1')],
    ['executeQueryWithBuffers', () => executeQueryWithBuffers('SELECT 1', [], [])],
  ]

  it.each(runs)('%s loads spatial and not h3, which no query uses', async (_, run) => {
    await run()
    expect(queries.some((sql) => /LOAD spatial/i.test(sql))).toBe(true)
    expect(queries.some((sql) => /h3/i.test(sql))).toBe(false)
  })

  // duckdb-wasm#2199: if spatial loads before the coordinate systems do,
  // reading a GeoParquet file with an OGC:CRS84 column fails with
  // "stoi: no conversion".
  it.each(runs)('%s reads the coordinate systems before loading spatial', async (_, run) => {
    await run()
    const crs = queries.findIndex((sql) => /duckdb_coordinate_systems\(\)/.test(sql))
    const spatial = queries.findIndex((sql) => /LOAD spatial/i.test(sql))
    expect(crs).toBeGreaterThanOrEqual(0)
    expect(crs).toBeLessThan(spatial)
  })
})
