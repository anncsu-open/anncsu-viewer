# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.2.0",
#     "pytest",
# ]
# ///
"""Tests for ISTAT boundary-based out-of-bounds detection.

Usage:
    uv run --with duckdb --with pytest -- pytest scripts/test_out_of_bounds.py -v
"""

import duckdb
import pytest


@pytest.fixture
def db():
    """DuckDB connection with spatial extension and test boundaries."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    # Create test boundaries: two small squares as municipality polygons
    # Comune A: centered at (12.0, 42.0), ~0.1 degree box
    # Comune B: centered at (15.0, 38.0), ~0.1 degree box (far away, like Sicily)
    con.execute("""
        CREATE TABLE boundaries AS
        SELECT * FROM (VALUES
            ('001001', ST_GeomFromText('POLYGON((11.95 41.95, 12.05 41.95, 12.05 42.05, 11.95 42.05, 11.95 41.95))')),
            ('002002', ST_GeomFromText('POLYGON((14.95 37.95, 15.05 37.95, 15.05 38.05, 14.95 38.05, 14.95 37.95))'))
        ) AS t(codice_istat, geometry)
    """)

    return con


OOB_THRESHOLD_M = 110


def flag_out_of_bounds(con) -> None:
    """Add oob_distance_m and out_of_bounds columns using ST_Contains with boundaries.

    - oob_distance_m: distance in meters from the boundary (NULL if inside)
    - out_of_bounds: true only if oob_distance_m > OOB_THRESHOLD_M
    """
    con.execute(f"""
        CREATE TABLE addresses_validated AS
        SELECT
            a.*,
            CASE
                WHEN b.geometry IS NULL THEN NULL
                WHEN ST_Contains(b.geometry, a.geometry) THEN NULL
                ELSE ROUND(ST_Distance(b.geometry, a.geometry)::DOUBLE * 111000, 2)
            END AS oob_distance_m,
            CASE
                WHEN b.geometry IS NULL THEN NULL
                WHEN ST_Contains(b.geometry, a.geometry) THEN false
                WHEN ST_Distance(b.geometry, a.geometry)::DOUBLE * 111000 > {OOB_THRESHOLD_M} THEN true
                ELSE false
            END AS out_of_bounds
        FROM addresses a
        LEFT JOIN boundaries b ON a.CODICE_ISTAT = b.codice_istat
    """)

    con.execute("DROP TABLE addresses")
    con.execute("ALTER TABLE addresses_validated RENAME TO addresses")


class TestOutOfBoundsDetection:
    """Tests for ISTAT boundary-based out-of-bounds detection."""

    def test_address_inside_its_comune_is_not_flagged(self, db):
        """An address with coordinates inside its declared comune boundary."""
        db.execute("""
            CREATE TABLE addresses AS
            SELECT '001001' AS CODICE_ISTAT, 'Comune A' AS NOME_COMUNE,
                   'VIA ROMA' AS ODONIMO, 1 AS CIVICO,
                   12.0 AS longitude, 42.0 AS latitude,
                   ST_Point(12.0, 42.0) AS geometry
        """)

        flag_out_of_bounds(db)
        result = db.execute("SELECT out_of_bounds FROM addresses").fetchone()
        assert result[0] is False

    def test_address_outside_its_comune_is_flagged(self, db):
        """An address declared in Comune B but located in Comune A area."""
        db.execute("""
            CREATE TABLE addresses AS
            SELECT '002002' AS CODICE_ISTAT, 'Comune B' AS NOME_COMUNE,
                   'VIA FONTANA' AS ODONIMO, 7 AS CIVICO,
                   12.0 AS longitude, 42.0 AS latitude,
                   ST_Point(12.0, 42.0) AS geometry
        """)

        flag_out_of_bounds(db)
        result = db.execute("SELECT out_of_bounds FROM addresses").fetchone()
        assert result[0] is True

    def test_address_without_boundary_data_is_null(self, db):
        """An address whose comune has no boundary polygon."""
        db.execute("""
            CREATE TABLE addresses AS
            SELECT '999999' AS CODICE_ISTAT, 'Unknown' AS NOME_COMUNE,
                   'VIA TEST' AS ODONIMO, 1 AS CIVICO,
                   12.0 AS longitude, 42.0 AS latitude,
                   ST_Point(12.0, 42.0) AS geometry
        """)

        flag_out_of_bounds(db)
        result = db.execute("SELECT out_of_bounds FROM addresses").fetchone()
        assert result[0] is None

    def test_mixed_addresses_flagged_correctly(self, db):
        """Multiple addresses: valid, out-of-bounds, and unknown."""
        db.execute("""
            CREATE TABLE addresses AS
            SELECT * FROM (VALUES
                ('001001', 'Comune A', 'VIA ROMA', 1, 12.0, 42.0, ST_Point(12.0, 42.0)),
                ('002002', 'Comune B', 'VIA FONTANA', 7, 12.0, 42.0, ST_Point(12.0, 42.0)),
                ('002002', 'Comune B', 'VIA MARE', 1, 15.0, 38.0, ST_Point(15.0, 38.0)),
                ('999999', 'Unknown', 'VIA TEST', 1, 12.0, 42.0, ST_Point(12.0, 42.0))
            ) AS t(CODICE_ISTAT, NOME_COMUNE, ODONIMO, CIVICO, longitude, latitude, geometry)
        """)

        flag_out_of_bounds(db)

        results = db.execute(
            "SELECT ODONIMO, CIVICO, out_of_bounds FROM addresses ORDER BY ODONIMO, CIVICO"
        ).fetchall()

        # VIA FONTANA 7 — Comune B address at Comune A coords → out of bounds
        assert results[0] == ("VIA FONTANA", 7, True)
        # VIA MARE 1 — Comune B address at Comune B coords → valid
        assert results[1] == ("VIA MARE", 1, False)
        # VIA ROMA 1 — Comune A address at Comune A coords → valid
        assert results[2] == ("VIA ROMA", 1, False)
        # VIA TEST 1 — Unknown comune → NULL
        assert results[3] == ("VIA TEST", 1, None)

    def test_address_just_outside_boundary_is_not_flagged(self, db):
        """An address just outside its boundary (< 110m) should not be flagged.

        Comune A box edge is at lon=12.05. Point at 12.0505 is ~55m outside.
        """
        db.execute("""
            CREATE TABLE addresses AS
            SELECT '001001' AS CODICE_ISTAT, 'Comune A' AS NOME_COMUNE,
                   'VIA CONFINE' AS ODONIMO, 1 AS CIVICO,
                   12.0505 AS longitude, 42.0 AS latitude,
                   ST_Point(12.0505, 42.0) AS geometry
        """)

        flag_out_of_bounds(db)
        result = db.execute(
            "SELECT out_of_bounds, oob_distance_m FROM addresses"
        ).fetchone()
        assert result[0] is False, "Address within 110m of boundary should not be flagged"
        assert result[1] is not None, "oob_distance_m should be populated"
        assert result[1] > 0, "oob_distance_m should be positive"
        assert result[1] < 110, f"oob_distance_m should be < 110m, got {result[1]}"

    def test_oob_distance_is_null_for_inside_address(self, db):
        """An address inside its boundary should have NULL oob_distance_m."""
        db.execute("""
            CREATE TABLE addresses AS
            SELECT '001001' AS CODICE_ISTAT, 'Comune A' AS NOME_COMUNE,
                   'VIA ROMA' AS ODONIMO, 1 AS CIVICO,
                   12.0 AS longitude, 42.0 AS latitude,
                   ST_Point(12.0, 42.0) AS geometry
        """)

        flag_out_of_bounds(db)
        result = db.execute("SELECT oob_distance_m FROM addresses").fetchone()
        assert result[0] is None

    def test_oob_distance_populated_for_outside_address(self, db):
        """An address outside its boundary should have a positive oob_distance_m."""
        db.execute("""
            CREATE TABLE addresses AS
            SELECT '002002' AS CODICE_ISTAT, 'Comune B' AS NOME_COMUNE,
                   'VIA FONTANA' AS ODONIMO, 7 AS CIVICO,
                   12.0 AS longitude, 42.0 AS latitude,
                   ST_Point(12.0, 42.0) AS geometry
        """)

        flag_out_of_bounds(db)
        result = db.execute("SELECT oob_distance_m FROM addresses").fetchone()
        assert result[0] is not None
        assert result[0] > 0

    def test_out_of_bounds_and_oob_distance_columns_exist(self, db):
        """Both out_of_bounds and oob_distance_m columns should be present."""
        db.execute("""
            CREATE TABLE addresses AS
            SELECT '001001' AS CODICE_ISTAT, 'Comune A' AS NOME_COMUNE,
                   'VIA ROMA' AS ODONIMO, 1 AS CIVICO,
                   12.0 AS longitude, 42.0 AS latitude,
                   ST_Point(12.0, 42.0) AS geometry
        """)

        flag_out_of_bounds(db)

        columns = [
            row[0] for row in db.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'addresses'"
            ).fetchall()
        ]
        assert "out_of_bounds" in columns
        assert "oob_distance_m" in columns

    def test_preserves_all_original_columns(self, db):
        """The validation should preserve all original columns."""
        db.execute("""
            CREATE TABLE addresses AS
            SELECT '001001' AS CODICE_ISTAT, 'Comune A' AS NOME_COMUNE,
                   'VIA ROMA' AS ODONIMO, 1 AS CIVICO,
                   12.0 AS longitude, 42.0 AS latitude,
                   ST_Point(12.0, 42.0) AS geometry
        """)

        flag_out_of_bounds(db)

        result = db.execute(
            "SELECT CODICE_ISTAT, NOME_COMUNE, ODONIMO, CIVICO, "
            "CAST(longitude AS DOUBLE) as lon, CAST(latitude AS DOUBLE) as lat FROM addresses"
        ).fetchone()
        assert result == ("001001", "Comune A", "VIA ROMA", 1, 12.0, 42.0)

    def test_counts_out_of_bounds(self, db):
        """Should be able to count flagged addresses."""
        db.execute("""
            CREATE TABLE addresses AS
            SELECT * FROM (VALUES
                ('001001', 'Comune A', 'VIA ROMA', 1, 12.0, 42.0, ST_Point(12.0, 42.0)),
                ('002002', 'Comune B', 'VIA FONTANA', 7, 12.0, 42.0, ST_Point(12.0, 42.0)),
                ('002002', 'Comune B', 'VIA GARIBALDI', 3, 12.0, 42.0, ST_Point(12.0, 42.0))
            ) AS t(CODICE_ISTAT, NOME_COMUNE, ODONIMO, CIVICO, longitude, latitude, geometry)
        """)

        flag_out_of_bounds(db)

        total = db.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
        flagged = db.execute(
            "SELECT COUNT(*) FROM addresses WHERE out_of_bounds = true"
        ).fetchone()[0]
        valid = db.execute(
            "SELECT COUNT(*) FROM addresses WHERE out_of_bounds = false"
        ).fetchone()[0]

        assert total == 3
        assert flagged == 2  # VIA FONTANA and VIA GARIBALDI (Comune B at Comune A coords)
        assert valid == 1  # VIA ROMA (Comune A at Comune A coords)
