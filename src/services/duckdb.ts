import * as duckdb from '@duckdb/duckdb-wasm'
import duckdb_wasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url'
import mvp_worker from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url'
import duckdb_wasm_next from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url'
import eh_worker from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url'
import type { FeatureCollection, Polygon } from 'geojson'

const MANUAL_BUNDLES = {
  mvp: {
    mainModule: duckdb_wasm,
    mainWorker: mvp_worker,
  },
  eh: {
    mainModule: duckdb_wasm_next,
    mainWorker: eh_worker,
  },
}

interface DuckResponseProperties {
  count: number
}
interface DuckResponseObject extends DuckResponseProperties {
  geometry: string
}

const logger = new duckdb.ConsoleLogger()

export async function executeQuery(
  queryInput: string,
): Promise<FeatureCollection<Polygon, DuckResponseProperties> | undefined> {
  let query = queryInput
  const bundle = await duckdb.selectBundle(MANUAL_BUNDLES)
  const worker = new Worker(bundle.mainWorker)
  const db = new duckdb.AsyncDuckDB(logger, worker)
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker)
  const conn = await db.connect()

  await conn.query('INSTALL spatial;LOAD spatial;')
  await conn.query('INSTALL h3 FROM community;LOAD h3;')

  // Register HTTP URLs found in the query so DuckDB WASM can fetch them
  const httpUrls = query.match(/https?:\/\/[^\s'")]+/g) || []
  for (const url of httpUrls) {
    await db.registerFileURL(url, url, duckdb.DuckDBDataProtocol.HTTP, false)
  }

  let featureCollection: FeatureCollection<Polygon, DuckResponseProperties>
  try {
    const res = await conn.query(query)

    featureCollection = {
      type: 'FeatureCollection',
      features: res.toArray().map((d: DuckResponseObject) => {
        const { geometry, ...properties } = d
        return {
          type: 'Feature',
          geometry: JSON.parse(geometry) as Polygon,
          properties,
        }
      }),
    }
  } catch (error) {
    console.error('Error executing query:', error)
  } finally {
    await conn.close()
    await db.terminate()
    await worker.terminate()
  }
  return featureCollection
}

export async function executeQueryWithBuffers(
  query: string,
  buffers: ArrayBuffer[],
  fileNames: string[],
): Promise<FeatureCollection<Polygon, DuckResponseProperties> | undefined> {
  const bundle = await duckdb.selectBundle(MANUAL_BUNDLES)
  const worker = new Worker(bundle.mainWorker)
  const db = new duckdb.AsyncDuckDB(logger, worker)
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker)

  // Register each buffer as a named file
  for (let i = 0; i < buffers.length; i++) {
    await db.registerFileBuffer(fileNames[i], new Uint8Array(buffers[i]))
  }

  const conn = await db.connect()
  await conn.query('INSTALL spatial;LOAD spatial;')

  let featureCollection: FeatureCollection<Polygon, DuckResponseProperties>
  try {
    const res = await conn.query(query)

    featureCollection = {
      type: 'FeatureCollection',
      features: res.toArray().map((d: DuckResponseObject) => {
        const { geometry, ...properties } = d
        return {
          type: 'Feature',
          geometry: JSON.parse(geometry) as Polygon,
          properties,
        }
      }),
    }
  } catch (error) {
    console.error('Error executing query:', error)
  } finally {
    await conn.close()
    await db.terminate()
    await worker.terminate()
  }
  return featureCollection
}
