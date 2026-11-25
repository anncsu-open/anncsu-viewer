import * as duckdb from '@duckdb/duckdb-wasm'
import base_wasm from '@duckdb/duckdb-wasm/dist/duckdb-base.wasm?url'
import base_worker from '@duckdb/duckdb-wasm/dist/duckdb-browser-base.worker.js?url'
import type { FeatureCollection, Geometry } from 'geojson'

// Only the single-threaded bundle: the threads one needs cross-origin
// isolation, which GitHub Pages cannot provide.
const MANUAL_BUNDLES: duckdb.DuckDBBundles = {
  base: {
    mainModule: base_wasm,
    mainWorker: base_worker,
  },
}

interface DuckResponseProperties {
  count: number
}
interface DuckResponseObject extends DuckResponseProperties {
  geometry: string
}

const logger = new duckdb.ConsoleLogger()

// duckdb-wasm#2199: if spatial loads before DuckDB has read its coordinate
// systems, every later read of an OGC:CRS84 geometry column, as in our
// GeoParquet files, fails with "stoi: no conversion".
async function loadSpatial(conn: duckdb.AsyncDuckDBConnection) {
  await conn.query('SELECT count(*) FROM duckdb_coordinate_systems()')
  await conn.query('INSTALL spatial;LOAD spatial;')
}

export async function executeQuery(
  queryInput: string,
): Promise<FeatureCollection<Geometry, DuckResponseProperties> | undefined> {
  let query = queryInput
  const bundle = await duckdb.selectBundle(MANUAL_BUNDLES)
  const worker = new Worker(bundle.mainWorker)
  const db = new duckdb.AsyncDuckDB(logger, worker)
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker)
  const conn = await db.connect()

  await loadSpatial(conn)

  // Register HTTP URLs found in the query so DuckDB WASM can fetch them
  const httpUrls = query.match(/https?:\/\/[^\s'")]+/g) || []
  for (const url of httpUrls) {
    await db.registerFileURL(url, url, duckdb.DuckDBDataProtocol.HTTP, false)
  }

  let featureCollection: FeatureCollection<Geometry, DuckResponseProperties>
  try {
    const res = await conn.query(query)

    featureCollection = {
      type: 'FeatureCollection',
      features: res.toArray().map((d: DuckResponseObject) => {
        const { geometry, ...properties } = d
        return {
          type: 'Feature',
          geometry: JSON.parse(geometry) as Geometry,
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
): Promise<FeatureCollection<Geometry, DuckResponseProperties> | undefined> {
  const bundle = await duckdb.selectBundle(MANUAL_BUNDLES)
  const worker = new Worker(bundle.mainWorker)
  const db = new duckdb.AsyncDuckDB(logger, worker)
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker)

  // Register each buffer as a named file
  for (let i = 0; i < buffers.length; i++) {
    await db.registerFileBuffer(fileNames[i], new Uint8Array(buffers[i]))
  }

  const conn = await db.connect()
  await loadSpatial(conn)

  let featureCollection: FeatureCollection<Geometry, DuckResponseProperties>
  try {
    const res = await conn.query(query)

    featureCollection = {
      type: 'FeatureCollection',
      features: res.toArray().map((d: DuckResponseObject) => {
        const { geometry, ...properties } = d
        return {
          type: 'Feature',
          geometry: JSON.parse(geometry) as Geometry,
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
