import { describe, it, expect } from 'vitest'
import {
  h3DistributionQuery,
  spatialAggregationQuery,
  anncsuAddressesQuery,
  anncsuPlacesQuery,
} from '@/services/queries'

describe('SQL queries', () => {
  it('h3DistributionQuery selects geometry and count', () => {
    expect(h3DistributionQuery).toContain('SELECT geometry, count')
    expect(h3DistributionQuery).toContain('H3_latlng_to_cell')
    expect(h3DistributionQuery).toContain("categories.main = 'hotel'")
    expect(h3DistributionQuery).toContain("region = 'US-UT'")
  })

  it('spatialAggregationQuery joins divisions with places', () => {
    expect(spatialAggregationQuery).toContain('ST_AsGeoJSON(area_geom) as geometry')
    expect(spatialAggregationQuery).toContain('LEFT JOIN schools ON ST_Contains')
    expect(spatialAggregationQuery).toContain('CAST(count(place_geom) as INT) as count')
  })

  it('anncsuAddressesQuery selects addresses with name', () => {
    expect(anncsuAddressesQuery).toContain('FROM addresses')
    expect(anncsuAddressesQuery).toContain('ODONIMO')
    expect(anncsuAddressesQuery).toContain('CIVICO')
    expect(anncsuAddressesQuery).toContain('as name')
    expect(anncsuAddressesQuery).toContain('1 as count')
    expect(anncsuAddressesQuery).toContain('ST_AsGeoJSON(geometry) as geometry')
  })

  it('anncsuPlacesQuery selects places with name and category', () => {
    expect(anncsuPlacesQuery).toContain('FROM places')
    expect(anncsuPlacesQuery).toContain('names.primary as name')
    expect(anncsuPlacesQuery).toContain('categories.primary as category')
    expect(anncsuPlacesQuery).toContain('1 as count')
  })

  it('all queries include a geometry column', () => {
    const queries = [h3DistributionQuery, spatialAggregationQuery, anncsuAddressesQuery, anncsuPlacesQuery]
    for (const q of queries) {
      expect(q.toLowerCase()).toContain('geometry')
    }
  })

  it('all queries include a count column', () => {
    const queries = [h3DistributionQuery, spatialAggregationQuery, anncsuAddressesQuery, anncsuPlacesQuery]
    for (const q of queries) {
      expect(q.toLowerCase()).toContain('count')
    }
  })
})
