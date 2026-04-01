INSTALL spatial; LOAD spatial;

WITH bounds AS (
    SELECT codice_istat, nome_comune, geometry
    FROM read_parquet('data/istat-boundaries.parquet')
),
gap_pairs AS (
    SELECT
        ROUND(ST_Distance(a.geometry, b.geometry)::DOUBLE * 111000, 2) AS gap_m
    FROM bounds a, bounds b
    WHERE a.codice_istat < b.codice_istat
      AND ST_DWithin(a.geometry, b.geometry, 0.002)
      AND ST_Distance(a.geometry, b.geometry) > 0.000001
      AND NOT ST_Touches(a.geometry, b.geometry)
      AND NOT ST_Overlaps(a.geometry, b.geometry)
      AND NOT ST_Intersects(a.geometry, b.geometry)
)
SELECT
    CASE
        WHEN gap_m <= 10 THEN '0-10m'
        WHEN gap_m <= 50 THEN '10-50m'
        WHEN gap_m <= 100 THEN '50-100m'
        WHEN gap_m <= 150 THEN '100-150m'
        WHEN gap_m <= 200 THEN '150-200m'
        ELSE '200m+'
    END AS bucket,
    COUNT(*) AS cnt,
    MIN(gap_m) AS min_m,
    MAX(gap_m) AS max_m
FROM gap_pairs
GROUP BY 1
ORDER BY min_m;
