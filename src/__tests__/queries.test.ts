import { describe, it, expect } from 'vitest'
import {
  h3DistributionQuery,
  spatialAggregationQuery,
  vaconeAddressesQuery,
  vaconePlacesQuery,
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

  it('vaconeAddressesQuery selects addresses with name', () => {
    expect(vaconeAddressesQuery).toContain('FROM addresses')
    expect(vaconeAddressesQuery).toContain('ODONIMO')
    expect(vaconeAddressesQuery).toContain('CIVICO')
    expect(vaconeAddressesQuery).toContain('as name')
    expect(vaconeAddressesQuery).toContain('1 as count')
    expect(vaconeAddressesQuery).toContain('ST_AsGeoJSON(geometry) as geometry')
  })

  it('vaconePlacesQuery selects places with name and category', () => {
    expect(vaconePlacesQuery).toContain('FROM places')
    expect(vaconePlacesQuery).toContain('names.primary as name')
    expect(vaconePlacesQuery).toContain('categories.primary as category')
    expect(vaconePlacesQuery).toContain('1 as count')
  })

  it('all queries include a geometry column', () => {
    const queries = [h3DistributionQuery, spatialAggregationQuery, vaconeAddressesQuery, vaconePlacesQuery]
    for (const q of queries) {
      expect(q.toLowerCase()).toContain('geometry')
    }
  })

  it('all queries include a count column', () => {
    const queries = [h3DistributionQuery, spatialAggregationQuery, vaconeAddressesQuery, vaconePlacesQuery]
    for (const q of queries) {
      expect(q.toLowerCase()).toContain('count')
    }
  })
})
