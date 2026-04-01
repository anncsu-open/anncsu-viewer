# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.2.0",
#     "pytest",
# ]
# ///
"""Tests for ISTAT boundary parquet generation.

Usage:
    uv run --with duckdb --with pytest -- pytest scripts/test_boundaries.py -v
"""

import duckdb
import pytest
from pathlib import Path

BOUNDARIES_FILE = Path(__file__).resolve().parent.parent / "data" / "istat-boundaries.parquet"


@pytest.fixture
def db():
    """DuckDB connection with spatial extension."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    return con


@pytest.mark.skipif(not BOUNDARIES_FILE.exists(), reason="boundaries parquet not generated")
class TestBoundariesParquet:
    """Tests for the generated istat-boundaries.parquet."""

    def test_has_expected_columns(self, db):
        """Should have codice_istat, nome_comune, geometry columns."""
        columns = [
            row[0] for row in db.execute(
                f"SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{BOUNDARIES_FILE}'))"
            ).fetchall()
        ]
        assert "codice_istat" in columns
        assert "nome_comune" in columns
        assert "geometry" in columns

    def test_has_municipalities(self, db):
        """Should contain thousands of municipalities."""
        count = db.execute(
            f"SELECT COUNT(*) FROM read_parquet('{BOUNDARIES_FILE}')"
        ).fetchone()[0]
        assert count > 7000

    def test_coordinates_are_wgs84_lon_lat(self, db):
        """Boundary coordinates should be in WGS84 with X=longitude, Y=latitude.

        For Italy: longitude ~6-19, latitude ~35-48.
        X (ST_XMin/ST_XMax) should be longitude range.
        Y (ST_YMin/ST_YMax) should be latitude range.
        """
        # Check Roma boundary
        bbox = db.execute(f"""
            SELECT ST_XMin(geometry), ST_YMin(geometry),
                   ST_XMax(geometry), ST_YMax(geometry)
            FROM read_parquet('{BOUNDARIES_FILE}')
            WHERE codice_istat = '058091'
        """).fetchone()

        xmin, ymin, xmax, ymax = bbox
        # X should be longitude (12-13 for Roma)
        assert 11 < xmin < 14, f"xmin={xmin} not in longitude range for Roma"
        assert 11 < xmax < 14, f"xmax={xmax} not in longitude range for Roma"
        # Y should be latitude (41-43 for Roma)
        assert 40 < ymin < 44, f"ymin={ymin} not in latitude range for Roma"
        assert 40 < ymax < 44, f"ymax={ymax} not in latitude range for Roma"

    def test_roma_contains_roma_point(self, db):
        """A known point inside Roma should be contained by Roma boundary.

        Colosseum: lon=12.4924, lat=41.8902
        """
        result = db.execute(f"""
            SELECT ST_Contains(
                geometry,
                ST_Point(12.4924, 41.8902)
            )
            FROM read_parquet('{BOUNDARIES_FILE}')
            WHERE codice_istat = '058091'
        """).fetchone()
        assert result[0] is True, "Colosseum should be inside Roma boundary"

    def test_roma_does_not_contain_milano_point(self, db):
        """A point in Milano should NOT be contained by Roma boundary.

        Duomo di Milano: lon=9.1900, lat=45.4642
        """
        result = db.execute(f"""
            SELECT ST_Contains(
                geometry,
                ST_Point(9.1900, 45.4642)
            )
            FROM read_parquet('{BOUNDARIES_FILE}')
            WHERE codice_istat = '058091'
        """).fetchone()
        assert result[0] is False, "Duomo di Milano should NOT be inside Roma boundary"

    def test_roccafiorita_boundary_is_in_sicily(self, db):
        """Roccafiorita (ME) boundary should be in Sicily, not Lazio.

        Sicily: lon ~13-16, lat ~36-39
        """
        bbox = db.execute(f"""
            SELECT ST_XMin(geometry), ST_YMin(geometry),
                   ST_XMax(geometry), ST_YMax(geometry)
            FROM read_parquet('{BOUNDARIES_FILE}')
            WHERE codice_istat = '083071'
        """).fetchone()

        xmin, ymin, xmax, ymax = bbox
        # Roccafiorita is in Messina province, Sicily
        assert 14 < xmin < 16, f"xmin={xmin} not in Sicily longitude range"
        assert 37 < ymin < 39, f"ymin={ymin} not in Sicily latitude range"

    def test_frascati_point_not_in_roccafiorita(self, db):
        """The Frascati coordinates from issue #1 should NOT be in Roccafiorita."""
        result = db.execute(f"""
            SELECT ST_Contains(
                geometry,
                ST_Point(12.5094997, 41.9155018)
            )
            FROM read_parquet('{BOUNDARIES_FILE}')
            WHERE codice_istat = '083071'
        """).fetchone()
        assert result[0] is False, "Frascati coordinates should NOT be inside Roccafiorita"

    def test_all_polygons_are_valid(self, db):
        """All boundary polygons must be geometrically valid."""
        invalid = db.execute(f"""
            SELECT codice_istat, nome_comune
            FROM read_parquet('{BOUNDARIES_FILE}')
            WHERE NOT ST_IsValid(geometry)
        """).fetchall()
        assert invalid == [], f"Invalid polygons found: {invalid}"

    def test_no_genuine_gaps_between_adjacent_municipalities(self, db):
        """Adjacent municipalities must not have topological gaps between them.

        A genuine gap is a pair of municipalities that are close (within 0.002 deg)
        but don't touch/intersect, AND no other municipality covers the midpoint
        of the gap. The only expected exception is Arzachena-La Maddalena (islands).
        """
        gaps = db.execute(f"""
            WITH bounds AS (
                SELECT codice_istat, nome_comune, geometry
                FROM read_parquet('{BOUNDARIES_FILE}')
            ),
            candidates AS (
                SELECT
                    a.codice_istat AS istat_a, a.nome_comune AS name_a,
                    b.codice_istat AS istat_b, b.nome_comune AS name_b,
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
            -- Exclude marine gap: Arzachena-La Maddalena (islands)
            AND NOT (c.istat_a = '090006' AND c.istat_b = '090035')
            ORDER BY c.gap_m DESC
        """).fetchall()
        assert gaps == [], f"Genuine topological gaps found: {gaps}"
