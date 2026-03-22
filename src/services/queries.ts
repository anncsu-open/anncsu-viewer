export const h3DistributionQuery = `WITH areas AS (
  SELECT
    names.primary AS NAME,
    geometry AS area_geom
  FROM divisions
  WHERE
    subtype = 'locality'
    AND region = 'US-UT'
),
schools AS (
  SELECT geometry AS place_geom
  FROM places,
    areas
  WHERE
    categories.main = 'hotel'
    AND St_within(place_geom, area_geom)
),
h3 AS (
  SELECT
    H3_latlng_to_cell(St_y(place_geom), St_x(place_geom), 6) AS h3_cell,
    Cast(Count(*) AS INT) AS count,
    St_asgeojson(St_geomfromtext(H3_cell_to_boundary_wkt(h3_cell))) AS geometry
  FROM schools
  GROUP BY h3_cell
)
SELECT geometry, count
FROM h3`

export const spatialAggregationQuery = `WITH areas AS (
  SELECT names.primary as name,
         geometry as area_geom
  FROM divisions
  WHERE subtype = 'locality'
    AND region = 'US-UT'
),
schools AS (SELECT geometry as place_geom
  FROM places
  WHERE categories.main = 'hotel'
)
SELECT name, ST_AsGeoJSON(area_geom) as geometry,
       CAST(count(place_geom) as INT) as count
FROM areas
       LEFT JOIN schools ON ST_Contains(area_geom, place_geom)
GROUP BY area_geom, name`

export const anncsuAddressesQuery = `SELECT
  ST_AsGeoJSON(geometry) as geometry,
  ODONIMO || ' ' || COALESCE(CAST(CIVICO AS VARCHAR), '') || COALESCE(' ' || ESPONENTE, '') as name,
  1 as count
FROM addresses`

export const anncsuPlacesQuery = `SELECT
  ST_AsGeoJSON(geometry) as geometry,
  names.primary as name,
  categories.primary as category,
  1 as count
FROM places`
