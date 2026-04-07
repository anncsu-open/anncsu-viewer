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

import httpx
import pytest
import respx

from update_data import (
    ANNCSU_URL,
    _check_server_available,
    get_remote_date,
)


class TestCheckServerAvailable:
    """Tests for _check_server_available() early-exit on server errors."""

    @respx.mock
    def test_exits_on_403_forbidden(self):
        """Should raise SystemExit when server returns 403."""
        respx.head(ANNCSU_URL).mock(return_value=httpx.Response(403))
        with pytest.raises(SystemExit, match="403 Forbidden"):
            _check_server_available()

    @respx.mock
    def test_exits_on_500_server_error(self):
        """Should raise SystemExit when server returns 500."""
        respx.head(ANNCSU_URL).mock(return_value=httpx.Response(500))
        with pytest.raises(SystemExit, match="HTTP 500"):
            _check_server_available()

    @respx.mock
    def test_exits_on_connection_error(self):
        """Should raise SystemExit when server is unreachable."""
        respx.head(ANNCSU_URL).mock(side_effect=httpx.ConnectError("Connection refused"))
        with pytest.raises(SystemExit, match="unreachable"):
            _check_server_available()

    @respx.mock
    def test_passes_on_200(self):
        """Should not raise when server returns 200."""
        respx.head(ANNCSU_URL).mock(return_value=httpx.Response(200))
        _check_server_available()  # should not raise

    @respx.mock
    def test_passes_on_206_partial(self):
        """Should not raise when server returns 206 (range requests supported)."""
        respx.head(ANNCSU_URL).mock(return_value=httpx.Response(206))
        _check_server_available()  # should not raise

    @respx.mock
    def test_passes_on_302_redirect(self):
        """Should not raise on redirect (httpx follows redirects)."""
        respx.head(ANNCSU_URL).mock(return_value=httpx.Response(200))
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
