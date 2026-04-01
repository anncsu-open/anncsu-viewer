INSTALL spatial; LOAD spatial;

-- Find genuine topological gaps: pairs of comuni that are close
-- but don't touch, AND no other comune covers the space between them.
WITH bounds AS (
    SELECT codice_istat, nome_comune, geometry
    FROM read_parquet('data/istat-boundaries.parquet')
),
candidates AS (
    SELECT
        a.codice_istat AS istat_a, a.nome_comune AS name_a, a.geometry AS geom_a,
        b.codice_istat AS istat_b, b.nome_comune AS name_b, b.geometry AS geom_b,
        ST_Distance(a.geometry, b.geometry)::DOUBLE AS gap_deg,
        ROUND(ST_Distance(a.geometry, b.geometry)::DOUBLE * 111000, 2) AS gap_m,
        ST_Centroid(ST_ShortestLine(a.geometry, b.geometry)) AS midpoint
    FROM bounds a, bounds b
    WHERE a.codice_istat < b.codice_istat
      AND ST_DWithin(a.geometry, b.geometry, 0.002)
      AND ST_Distance(a.geometry, b.geometry) > 0.000001
      AND NOT ST_Touches(a.geometry, b.geometry)
      AND NOT ST_Overlaps(a.geometry, b.geometry)
      AND NOT ST_Intersects(a.geometry, b.geometry)
)
SELECT c.istat_a, c.name_a, c.istat_b, c.name_b, c.gap_m
FROM candidates c
WHERE NOT EXISTS (
    SELECT 1
    FROM bounds o
    WHERE o.codice_istat != c.istat_a
      AND o.codice_istat != c.istat_b
      AND ST_Contains(o.geometry, c.midpoint)
)
ORDER BY c.gap_m DESC;
