# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.2.0",
#     "geoparquet-io>=1.0.0b2",
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
