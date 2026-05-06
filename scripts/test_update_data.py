# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.5.2",
#     "geoparquet-io>=1.1.1",
#     "gpio-pmtiles",
#     "httpx",
#     "pytest",
#     "respx",
#     "typer",
# ]
# ///
"""Tests for update_data.py server availability and download resilience.

Usage:
    uv run --with httpx --with pytest --with respx --with typer -- pytest scripts/test_update_data.py -v
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from update_data import (
    ANNCSU_URL,
    MARKER_FILE,
    _check_server_available,
    _check_tippecanoe,
    _clean_tiles_dir,
    _validate_row_count,
    _validate_tile_row_count,
    csv_to_parquet,
    enhance_parquet,
    generate_comuni_h3,
    get_remote_date,
    is_update_needed,
)


class TestCheckServerAvailable:
    """Tests for _check_server_available() early-exit on server errors.

    Uses GET with Range: bytes=0-0 (not HEAD) because the Akamai CDN
    in front of the ANNCSU portal blocks HEAD requests.
    """

    @respx.mock
    def test_exits_on_403_forbidden(self):
        """Should raise SystemExit when server returns 403."""
        respx.get(ANNCSU_URL).mock(return_value=httpx.Response(403))
        with pytest.raises(SystemExit, match="403 Forbidden"):
            _check_server_available()

    @respx.mock
    def test_exits_on_500_server_error(self):
        """Should raise SystemExit when server returns 500."""
        respx.get(ANNCSU_URL).mock(return_value=httpx.Response(500))
        with pytest.raises(SystemExit, match="HTTP 500"):
            _check_server_available()

    @respx.mock
    def test_exits_on_connection_error(self):
        """Should raise SystemExit when server is unreachable."""
        respx.get(ANNCSU_URL).mock(side_effect=httpx.ConnectError("Connection refused"))
        with pytest.raises(SystemExit, match="unreachable"):
            _check_server_available()

    @respx.mock
    def test_passes_on_200(self):
        """Should not raise when server returns 200."""
        respx.get(ANNCSU_URL).mock(return_value=httpx.Response(200))
        _check_server_available()  # should not raise

    @respx.mock
    def test_passes_on_206_partial(self):
        """Should not raise when server returns 206 (range requests supported)."""
        respx.get(ANNCSU_URL).mock(return_value=httpx.Response(206))
        _check_server_available()  # should not raise

    @respx.mock
    def test_passes_on_302_redirect(self):
        """Should not raise on redirect (httpx follows redirects)."""
        respx.get(ANNCSU_URL).mock(return_value=httpx.Response(200))
        _check_server_available()  # should not raise


class TestGetRemoteDate:
    """Tests for get_remote_date() graceful error handling."""

    @respx.mock
    def test_returns_none_on_http_error(self):
        """Should return None (not crash) when server returns an error."""
        respx.get(ANNCSU_URL).mock(return_value=httpx.Response(403))
        result = get_remote_date()
        assert result is None

    @respx.mock
    def test_returns_none_on_connection_error(self):
        """Should return None when server is unreachable."""
        respx.get(ANNCSU_URL).mock(side_effect=httpx.ConnectError("Connection refused"))
        result = get_remote_date()
        assert result is None

    @respx.mock
    def test_parses_date_from_zip_tail(self):
        """Should extract date from CSV filename in zip tail."""
        content = b"some bytes INDIR_ITA_20260401.csv more bytes"
        respx.get(ANNCSU_URL).mock(return_value=httpx.Response(206, content=content))
        result = get_remote_date()
        assert result is not None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 1

    @respx.mock
    def test_returns_none_when_no_date_pattern(self):
        """Should return None when zip tail has no recognizable date."""
        content = b"some random bytes without any date pattern"
        respx.get(ANNCSU_URL).mock(return_value=httpx.Response(206, content=content))
        result = get_remote_date()
        assert result is None


class TestIsUpdateNeeded:
    """Tests for is_update_needed() using a marker file to track the last
    downloaded dataset date, instead of relying on git commit dates.

    The git commit date can be misleading: if someone commits the parquet
    on April 7 with data from April 1, git log says April 7 but the data
    is stale. A marker file records the actual remote dataset date.
    """

    def test_update_needed_when_remote_is_newer_than_marker(self, tmp_path):
        """Remote dataset (Apr 6) is newer than marker (Apr 1) → update needed."""
        marker = tmp_path / ".last_remote_date"
        marker.write_text("20260401")

        remote = datetime(2026, 4, 6, tzinfo=timezone.utc)
        with patch("update_data.MARKER_FILE", marker):
            assert is_update_needed(remote) is True

    def test_no_update_when_remote_matches_marker(self, tmp_path):
        """Remote dataset (Apr 6) matches marker (Apr 6) → no update."""
        marker = tmp_path / ".last_remote_date"
        marker.write_text("20260406")

        remote = datetime(2026, 4, 6, tzinfo=timezone.utc)
        with patch("update_data.MARKER_FILE", marker):
            assert is_update_needed(remote) is False

    def test_update_needed_when_no_marker_exists(self, tmp_path):
        """No marker file → first run, update needed."""
        marker = tmp_path / ".last_remote_date"  # does not exist

        remote = datetime(2026, 4, 6, tzinfo=timezone.utc)
        with patch("update_data.MARKER_FILE", marker):
            assert is_update_needed(remote) is True

    def test_update_needed_when_remote_date_unknown(self, tmp_path):
        """Cannot determine remote date → update to be safe."""
        marker = tmp_path / ".last_remote_date"
        marker.write_text("20260401")

        with patch("update_data.MARKER_FILE", marker):
            assert is_update_needed(None) is True


class TestCheckTippecanoe:
    """Tests for _check_tippecanoe() fail-fast when tippecanoe is missing."""

    def test_exits_when_tippecanoe_not_in_path(self):
        """Should raise SystemExit when tippecanoe is not found."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(SystemExit, match="tippecanoe"):
                _check_tippecanoe()

    def test_passes_when_tippecanoe_is_available(self):
        """Should not raise when tippecanoe is in PATH."""
        with patch("shutil.which", return_value="/usr/local/bin/tippecanoe"):
            _check_tippecanoe()  # should not raise


class TestGenerateComuniH3:
    """Tests for generate_comuni_h3() producing a correct mapping
    from each comune to ALL its H3 cells."""

    def test_includes_all_h3_cells_for_a_comune(self, tmp_path):
        """A comune with addresses in multiple H3 cells must list all of them."""
        import duckdb

        parquet = tmp_path / "test.parquet"
        output = tmp_path / "comuni-h3.json"

        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute("INSTALL h3 FROM community; LOAD h3;")

        # Create addresses for Scanno in two distinct H3 cells
        # Cell 1: center of Scanno (41.90, 13.88)
        # Cell 2: outskirts (41.93, 13.85) — different H3 res-5 cell
        con.execute(f"""
            COPY (
                SELECT * FROM (VALUES
                    ('066093', 'Scanno', 'VIA ROMA', 1, 13.88, 41.90,
                     ST_Point(13.88, 41.90)),
                    ('066093', 'Scanno', 'VIA NAPOLI', 2, 13.88, 41.90,
                     ST_Point(13.88, 41.90)),
                    ('066093', 'Scanno', 'VIA LAGO', 1, 13.85, 41.93,
                     ST_Point(13.85, 41.93))
                ) AS t(CODICE_ISTAT, NOME_COMUNE, ODONIMO, CIVICO,
                       longitude, latitude, geometry)
            ) TO '{parquet}' (FORMAT PARQUET)
        """)

        # Get expected H3 cells
        expected_cells = set()
        for lat, lon in [(41.90, 13.88), (41.93, 13.85)]:
            cell = con.execute(
                f"SELECT h3_h3_to_string(h3_latlng_to_cell({lat}, {lon}, 5))"
            ).fetchone()[0]
            expected_cells.add(cell)
        con.close()

        generate_comuni_h3(parquet, output)

        import json
        with open(output) as f:
            data = json.load(f)

        scanno = [c for c in data if c["nome_comune"] == "Scanno"]
        assert len(scanno) == 1
        actual_cells = set(scanno[0]["h3_cells"])
        assert actual_cells == expected_cells, (
            f"Expected cells {expected_cells}, got {actual_cells}"
        )

    def test_output_contains_all_comuni(self, tmp_path):
        """Every comune with addresses should appear in the output."""
        import duckdb

        parquet = tmp_path / "test.parquet"
        output = tmp_path / "comuni-h3.json"

        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute(f"""
            COPY (
                SELECT * FROM (VALUES
                    ('066093', 'Scanno', 'VIA ROMA', 1, 13.88, 41.90,
                     ST_Point(13.88, 41.90)),
                    ('058091', 'Roma', 'VIA VENETO', 1, 12.49, 41.90,
                     ST_Point(12.49, 41.90))
                ) AS t(CODICE_ISTAT, NOME_COMUNE, ODONIMO, CIVICO,
                       longitude, latitude, geometry)
            ) TO '{parquet}' (FORMAT PARQUET)
        """)
        con.close()

        generate_comuni_h3(parquet, output)

        import json
        with open(output) as f:
            data = json.load(f)

        nomi = {c["nome_comune"] for c in data}
        assert "Scanno" in nomi
        assert "Roma" in nomi


CSV_HEADER = (
    "CODICE_COMUNE;CODICE_ISTAT;PROGRESSIVO_NAZIONALE;CODICE_COMUNALE;"
    "ODONIMO;LOCALITA';DIZIONE_LINGUA1;DIZIONE_LINGUA2;PROGRESSIVO_ACCESSO;"
    "CODICE_COMUNALE_ACCESSO;CIVICO;ESPONENTE;SPECIFICITA;METRICO;"
    "PROGRESSIVO_SNC;COORD_X_COMUNE;COORD_Y_COMUNE;QUOTA;METODO\n"
)


def _write_csv(csv_path: Path, rows: list[str]) -> None:
    """Write a CSV with the canonical ANNCSU header and the given data rows."""
    csv_path.write_text(CSV_HEADER + "".join(r + "\n" for r in rows))


def _make_parquet(parquet_path: Path, num_rows: int) -> None:
    """Create a trivial parquet file with the requested number of rows."""
    import duckdb

    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT range AS x FROM range({num_rows})) "
        f"TO '{parquet_path}' (FORMAT PARQUET)"
    )
    con.close()


class TestValidateRowCount:
    """Tests for _validate_row_count() row-count sanity check.

    Catches silent row drops between CSV and parquet. The historic cause was
    DuckDB inferring BIGINT for QUOTA / CODICE_COMUNALE_ACCESSO and dropping
    rows whose values didn't fit (decimal quotes, alphanumeric Belfiore codes)
    when used together with ignore_errors=true.
    """

    def test_passes_when_counts_match(self, tmp_path):
        csv_path = tmp_path / "input.csv"
        _write_csv(csv_path, [
            "001001;010001;1;001001;VIA A;;;;1;001001;1;;;;0;7,684;45,066;200;1",
            "001001;010001;2;001001;VIA B;;;;1;001001;2;;;;0;7,684;45,066;100;1",
        ])
        parquet_path = tmp_path / "out.parquet"
        _make_parquet(parquet_path, 2)
        _validate_row_count(csv_path, parquet_path)  # should not raise

    def test_raises_on_count_mismatch(self, tmp_path):
        csv_path = tmp_path / "input.csv"
        _write_csv(csv_path, [
            "001001;010001;1;001001;VIA A;;;;1;001001;1;;;;0;7,684;45,066;200;1",
            "001001;010001;2;001001;VIA B;;;;1;001001;2;;;;0;7,684;45,066;100;1",
            "001001;010001;3;001001;VIA C;;;;1;001001;3;;;;0;7,684;45,066;300;1",
        ])
        parquet_path = tmp_path / "out.parquet"
        _make_parquet(parquet_path, 2)
        with pytest.raises(RuntimeError, match="Row count mismatch"):
            _validate_row_count(csv_path, parquet_path)

    def test_excludes_rows_without_coordinates(self, tmp_path):
        """Rows with empty COORD_X/Y are excluded from the CSV count."""
        csv_path = tmp_path / "input.csv"
        _write_csv(csv_path, [
            "001001;010001;1;001001;VIA A;;;;1;001001;1;;;;0;7,684;45,066;200;1",
            # no coordinates → not counted
            "001001;010001;2;001001;VIA B;;;;1;001001;2;;;;0;;;200;1",
            "001001;010001;3;001001;VIA C;;;;1;001001;3;;;;0;7,684;45,066;100;1",
        ])
        parquet_path = tmp_path / "out.parquet"
        _make_parquet(parquet_path, 2)  # only 2 rows had coords
        _validate_row_count(csv_path, parquet_path)  # should not raise

    def test_passes_when_decimal_quota_is_present(self, tmp_path):
        """The validator counts CSV rows in a way that survives decimal QUOTA values.

        If the validator inferred QUOTA as BIGINT, the row "QUOTA=58,77" would
        be silently dropped from the CSV count and a real divergence in the
        parquet would go unnoticed.
        """
        csv_path = tmp_path / "input.csv"
        _write_csv(csv_path, [
            "001001;010001;1;001001;VIA A;;;;1;001001;1;;;;0;7,684;45,066;200;1",
            "001001;010001;2;001001;VIA B;;;;1;001001;2;;;;0;7,684;45,066;58,77;1",
        ])
        parquet_path = tmp_path / "out.parquet"
        _make_parquet(parquet_path, 2)
        _validate_row_count(csv_path, parquet_path)  # should not raise

    def test_passes_when_alphanumeric_codice_accesso_is_present(self, tmp_path):
        """The validator must count rows with alphanumeric CODICE_COMUNALE_ACCESSO."""
        csv_path = tmp_path / "input.csv"
        _write_csv(csv_path, [
            "001001;010001;1;001001;VIA A;;;;1;001001;1;;;;0;7,684;45,066;200;1",
            "001001;010001;2;001001;VIA B;;;;2;G282;2;;;;0;7,684;45,066;100;1",
        ])
        parquet_path = tmp_path / "out.parquet"
        _make_parquet(parquet_path, 2)
        _validate_row_count(csv_path, parquet_path)  # should not raise


class TestCsvToParquet:
    """End-to-end tests for csv_to_parquet() ensuring no silent row drops.

    Regression coverage for a bug where ~2.4% of rows were dropped because
    DuckDB inferred QUOTA / CODICE_COMUNALE_ACCESSO as BIGINT and then,
    combined with ignore_errors=true, skipped rows whose values didn't fit.
    """

    def _setup_paths(self, tmp_path, monkeypatch) -> Path:
        comuni_path = tmp_path / "comuni.json"
        comuni_path.write_text(
            '[{"codice_istat": "010001", "nome_comune": "TestComune"}]'
        )
        output_path = tmp_path / "output.parquet"
        monkeypatch.setattr("update_data.OUTPUT_FILE", output_path)
        monkeypatch.setattr("update_data.COMUNI_FILE", comuni_path)
        # Skip the optional out-of-bounds enrichment step.
        monkeypatch.setattr(
            "update_data.BOUNDARIES_FILE", tmp_path / "no_boundaries.parquet"
        )
        return output_path

    def test_preserves_rows_with_decimal_quota(self, tmp_path, monkeypatch):
        """Rows whose QUOTA value is a decimal ('58,77') must not be dropped."""
        import duckdb

        csv_path = tmp_path / "input.csv"
        _write_csv(csv_path, [
            # First two rows have integer QUOTA — would let auto_detect infer BIGINT
            "001001;010001;1;001001;VIA A;;;;1;001001;1;;;;0;7,684;45,066;200;1",
            "001001;010001;2;001001;VIA B;;;;1;001001;2;;;;0;7,684;45,066;100;1",
            # Decimal QUOTA — historic regression: this row was silently dropped
            "001001;010001;3;001001;VIA C;;;;1;001001;3;;;;0;7,684;45,066;58,77;1",
        ])
        output_path = self._setup_paths(tmp_path, monkeypatch)

        csv_to_parquet(csv_path)

        con = duckdb.connect()
        count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{output_path}')"
        ).fetchone()[0]
        con.close()
        assert count == 3, f"Expected 3 rows, got {count} (decimal QUOTA dropped?)"

    def test_preserves_rows_with_alphanumeric_codice_accesso(
        self, tmp_path, monkeypatch
    ):
        """Rows with alphanumeric CODICE_COMUNALE_ACCESSO ('G282') must not be dropped."""
        import duckdb

        csv_path = tmp_path / "input.csv"
        _write_csv(csv_path, [
            "001001;010001;1;001001;VIA A;;;;1;001001;1;;;;0;7,684;45,066;200;1",
            "001001;010001;2;001001;VIA B;;;;2;001002;2;;;;0;7,684;45,066;100;1",
            # Belfiore-style code — historic regression: silently dropped
            "001001;010001;3;001001;VIA C;;;;3;G282;3;;;;0;7,684;45,066;300;1",
        ])
        output_path = self._setup_paths(tmp_path, monkeypatch)

        csv_to_parquet(csv_path)

        con = duckdb.connect()
        count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{output_path}')"
        ).fetchone()[0]
        con.close()
        assert count == 3, (
            f"Expected 3 rows, got {count} (alphanumeric CODICE_COMUNALE_ACCESSO dropped?)"
        )

    def test_drops_only_rows_without_coordinates(self, tmp_path, monkeypatch):
        """Only rows without COORD_X/Y should be filtered; everything else stays."""
        import duckdb

        csv_path = tmp_path / "input.csv"
        _write_csv(csv_path, [
            "001001;010001;1;001001;VIA A;;;;1;001001;1;;;;0;7,684;45,066;200;1",
            # Empty coordinates → must be filtered
            "001001;010001;2;001001;VIA B;;;;1;001001;2;;;;0;;;100;1",
            "001001;010001;3;001001;VIA C;;;;1;001001;3;;;;0;7,684;45,066;100;1",
        ])
        output_path = self._setup_paths(tmp_path, monkeypatch)

        csv_to_parquet(csv_path)

        con = duckdb.connect()
        count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{output_path}')"
        ).fetchone()[0]
        con.close()
        assert count == 2, f"Expected 2 rows (one without coords), got {count}"


class TestCleanTilesDir:
    """Tests for _clean_tiles_dir() removing stale files before re-partitioning.

    Regression coverage for a bug where geoparquet-io 1.1.1's partition_by_h3
    silently kept pre-existing files in the destination directory, leaving
    stale tiles from previous runs alongside the freshly written ones.
    """

    def test_removes_existing_files(self, tmp_path):
        tiles_dir = tmp_path / "tiles"
        (tiles_dir / "h3_cell=stale").mkdir(parents=True)
        stale_file = tiles_dir / "h3_cell=stale" / "stale.parquet"
        stale_file.write_bytes(b"old data")

        _clean_tiles_dir(tiles_dir)

        assert tiles_dir.exists(), "Tiles dir should be re-created"
        assert list(tiles_dir.glob("**/*")) == [], "Tiles dir should be empty"

    def test_creates_missing_dir(self, tmp_path):
        tiles_dir = tmp_path / "nonexistent" / "tiles"
        assert not tiles_dir.exists()

        _clean_tiles_dir(tiles_dir)

        assert tiles_dir.exists()


class TestValidateTileRowCount:
    """Tests for _validate_tile_row_count() catching tile/parquet drift."""

    def _make_parquet(self, path: Path, n_rows: int) -> None:
        import duckdb
        con = duckdb.connect()
        con.execute(
            f"COPY (SELECT range AS x FROM range({n_rows})) "
            f"TO '{path}' (FORMAT PARQUET)"
        )
        con.close()

    def test_passes_when_sum_of_tiles_matches_parquet(self, tmp_path):
        parquet_path = tmp_path / "input.parquet"
        self._make_parquet(parquet_path, 10)

        tiles_dir = tmp_path / "tiles"
        (tiles_dir / "h3_cell=a").mkdir(parents=True)
        (tiles_dir / "h3_cell=b").mkdir(parents=True)
        self._make_parquet(tiles_dir / "h3_cell=a" / "a.parquet", 6)
        self._make_parquet(tiles_dir / "h3_cell=b" / "b.parquet", 4)

        _validate_tile_row_count(parquet_path, tiles_dir)  # 6 + 4 == 10

    def test_raises_on_count_mismatch(self, tmp_path):
        parquet_path = tmp_path / "input.parquet"
        self._make_parquet(parquet_path, 10)

        tiles_dir = tmp_path / "tiles"
        (tiles_dir / "h3_cell=a").mkdir(parents=True)
        self._make_parquet(tiles_dir / "h3_cell=a" / "a.parquet", 5)

        with pytest.raises(RuntimeError, match="Tile row count mismatch"):
            _validate_tile_row_count(parquet_path, tiles_dir)


class TestEnhanceParquet:
    """Tests for enhance_parquet() — DuckDB-native add_bbox + Hilbert sort.

    Replaces geoparquet-io 1.1.1's add_bbox + sort_hilbert. Those operations
    loaded the entire table into memory, peaking near 6 GB on 20M rows and
    reliably killing GitHub-hosted runners. The DuckDB version streams the
    sort to disk so RAM stays bounded regardless of table size.

    These tests pin the contract so the replacement is verifiably equivalent
    to the geoparquet-io output the rest of the pipeline depends on.
    """

    def _write_input(self, path: Path, points: list[tuple[float, float]]) -> None:
        """Write a small parquet matching the schema csv_to_parquet outputs.

        Includes a few non-geometry columns so we can assert they survive.
        Casts coordinates to DOUBLE to match the production schema (otherwise
        DuckDB infers DECIMAL from numeric literals).
        """
        import duckdb

        rows = ",".join(
            f"('C{i:04d}', 'Comune{i}', "
            f"CAST({lon} AS DOUBLE), CAST({lat} AS DOUBLE), "
            f"ST_Point(CAST({lon} AS DOUBLE), CAST({lat} AS DOUBLE)))"
            for i, (lon, lat) in enumerate(points)
        )
        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute(f"""
            COPY (
                SELECT * FROM (VALUES {rows}) AS t(
                    CODICE_ISTAT, NOME_COMUNE, longitude, latitude, geometry
                )
            ) TO '{path}' (FORMAT PARQUET)
        """)
        con.close()

    def _read_rows(self, path: Path, columns: str = "*") -> list[tuple]:
        import duckdb
        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial;")
        rows = con.execute(
            f"SELECT {columns} FROM read_parquet('{path}')"
        ).fetchall()
        con.close()
        return rows

    def test_preserves_row_count(self, tmp_path):
        p = tmp_path / "in.parquet"
        self._write_input(p, [(12.0, 42.0), (9.0, 45.0), (15.0, 38.0)])
        enhance_parquet(p)
        assert len(self._read_rows(p)) == 3

    def test_adds_bbox_struct_column(self, tmp_path):
        p = tmp_path / "in.parquet"
        self._write_input(p, [(12.0, 42.0)])
        enhance_parquet(p)
        import duckdb
        con = duckdb.connect()
        cols = con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{p}')"
        ).fetchall()
        con.close()
        bbox_rows = [c for c in cols if c[0] == "bbox"]
        assert len(bbox_rows) == 1, f"Expected exactly one bbox column, got cols={cols}"
        bbox_type = bbox_rows[0][1].lower()
        for field in ("xmin", "ymin", "xmax", "ymax"):
            assert field in bbox_type, f"bbox struct missing {field}: {bbox_type}"

    def test_bbox_for_point_equals_lon_lat_for_all_four_fields(self, tmp_path):
        p = tmp_path / "in.parquet"
        self._write_input(p, [(12.5, 41.9)])
        enhance_parquet(p)
        import duckdb
        row = duckdb.connect().execute(f"""
            SELECT longitude, latitude,
                   bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax
            FROM read_parquet('{p}')
        """).fetchone()
        lon, lat, xmin, ymin, xmax, ymax = row
        assert xmin == lon and xmax == lon, f"bbox xmin/xmax should equal longitude={lon}"
        assert ymin == lat and ymax == lat, f"bbox ymin/ymax should equal latitude={lat}"

    def test_preserves_original_columns(self, tmp_path):
        p = tmp_path / "in.parquet"
        self._write_input(p, [(12.0, 42.0), (9.0, 45.0)])
        enhance_parquet(p)
        import duckdb
        col_names = {
            row[0] for row in duckdb.connect().execute(
                f"DESCRIBE SELECT * FROM read_parquet('{p}')"
            ).fetchall()
        }
        for required in (
            "CODICE_ISTAT", "NOME_COMUNE", "longitude", "latitude", "geometry"
        ):
            assert required in col_names, (
                f"Original column {required!r} dropped by enhance_parquet "
                f"(remaining: {col_names})"
            )

    def test_output_is_hilbert_sorted(self, tmp_path):
        """Rows must be reordered by Hilbert curve so spatial neighbours sit
        next to each other on disk. Verified by total Euclidean traversal:
        a Hilbert-sorted path is much shorter than a random shuffle."""
        import random

        p = tmp_path / "in.parquet"
        rng = random.Random(42)
        # 200 random points across Italy
        points = [(rng.uniform(7, 18), rng.uniform(36, 47)) for _ in range(200)]
        self._write_input(p, points)

        enhance_parquet(p)

        sorted_rows = self._read_rows(p, "longitude, latitude")

        def total_dist(seq):
            return sum(
                ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
                for a, b in zip(seq, seq[1:])
            )

        sorted_dist = total_dist(sorted_rows)
        random_dist = total_dist(points)
        assert sorted_dist < random_dist * 0.5, (
            f"Expected Hilbert sort to roughly halve traversal distance: "
            f"sorted={sorted_dist:.2f} random={random_dist:.2f}"
        )

    def test_output_partitionable_by_h3(self, tmp_path):
        """Integration check: the enhanced parquet must remain consumable by
        geoparquet-io's partition_by_h3, which is the next stage of the
        pipeline (partition_h3_tiles).

        Uses enough rows to clear geoparquet-io's "tiny partitions" minimum
        (>=100 rows/partition by default).
        """
        import random

        import geoparquet_io as gpio

        p = tmp_path / "in.parquet"
        rng = random.Random(0)
        # 300 points clustered around Roma — collapse to a single H3 res-5 cell
        # so geoparquet-io's row-per-partition floor is satisfied.
        points = [
            (12.49 + rng.uniform(-0.001, 0.001), 41.90 + rng.uniform(-0.001, 0.001))
            for _ in range(300)
        ]
        self._write_input(p, points)
        enhance_parquet(p)

        out_dir = tmp_path / "tiles"
        out_dir.mkdir()
        gpio.read(str(p)) \
            .add_h3(resolution=5) \
            .partition_by_h3(str(out_dir), resolution=5)

        files = list(out_dir.glob("**/*.parquet"))
        assert len(files) >= 1, "partition_by_h3 should produce at least one tile"

    def test_does_not_duplicate_or_drop_rows(self, tmp_path):
        """The set of (longitude, latitude) pairs is preserved exactly."""
        p = tmp_path / "in.parquet"
        points = [(12.0 + i * 0.1, 42.0 + i * 0.1) for i in range(50)]
        self._write_input(p, points)

        enhance_parquet(p)

        rows = self._read_rows(p, "longitude, latitude")
        assert sorted(rows) == sorted(points)
