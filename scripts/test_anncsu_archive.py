# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb==2.0.0",
#     "httpx",
#     "pytest",
#     "respx",
#     "typer",
# ]
# ///
"""Tests for anncsu_archive.py, the shared archive module for ANNCSU data."""

import io
import json
import zipfile
from pathlib import Path

import duckdb
import httpx
import pytest
from typer.testing import CliRunner

from anncsu_archive import (
    INDIRIZZARIO,
    QUOTE,
    STRADARIO,
    app,
    csv_to_raw_parquet,
    append_release,
    archive_latest,
    archive_third_party_parquet,
    archive_zip,
    download_zip,
    latest_release_date,
    normalize_csv,
    release_entry,
    remote_release_date,
)

STRADARIO_HEADER = (
    "CODICE_COMUNE;CODICE_ISTAT;PROGRESSIVO_NAZIONALE;CODICE_COMUNALE;ODONIMO;"
    "LOCALITA';TOTALE_ACCESSI;DIZIONE_LINGUA1;DIZIONE_LINGUA2;"
)
CLEAN_ROW = "H501;058091;1;;VIA ROMA;;12;;;"
SPLIT_ROW = (
    "B242;065017;1345847;;STRADA PROV.LE DUECENTOSESSANTOTTO BIS\n;;39;;;"
)
CIVICI_HEADER = ";".join(f"C{i}" for i in range(19))


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def read_repaired(path: Path) -> list[tuple]:
    return duckdb.sql(
        "SELECT * FROM read_csv(?, delim=';', header=true, quote=?, escape=?, "
        "all_varchar=true)",
        params=[str(path), QUOTE, QUOTE],
    ).fetchall()


def test_clean_file_is_returned_untouched(tmp_path):
    src = write(tmp_path / "s.csv", f"{STRADARIO_HEADER}\n{CLEAN_ROW}\n")
    path, count = normalize_csv(src)
    assert path == src
    assert count == 0
    assert not (tmp_path / "s.repaired.csv").exists()


def test_rejoins_a_record_split_by_a_line_feed(tmp_path):
    src = write(
        tmp_path / "s.csv", f"{STRADARIO_HEADER}\n{CLEAN_ROW}\n{SPLIT_ROW}\n"
    )
    path, count = normalize_csv(src)
    assert count == 1
    assert path == tmp_path / "s.repaired.csv"
    rows = read_repaired(path)
    assert len(rows) == 2
    assert rows[0][4] == "VIA ROMA"
    assert rows[1][4] == "STRADA PROV.LE DUECENTOSESSANTOTTO BIS\n"
    assert rows[1][6] == "39"


def test_rejoins_civici_records_too(tmp_path):
    clean = ";".join(f"v{i}" for i in range(19))
    cells = [f"v{i}" for i in range(19)]
    cells[4] = "VIA\nNUOVA"
    split = ";".join(cells)
    src = write(tmp_path / "c.csv", f"{CIVICI_HEADER}\n{clean}\n{split}\n")
    path, count = normalize_csv(src)
    assert count == 1
    rows = read_repaired(path)
    assert len(rows) == 2
    assert rows[1][4] == "VIA\nNUOVA"
    assert rows[1][18] == "v18"


def test_rejoins_a_record_split_over_three_lines(tmp_path):
    record = "B242;065017;1;;STRADA\nBIS;LOC\nALITA;39;;;"
    src = write(tmp_path / "s.csv", f"{STRADARIO_HEADER}\n{record}\n")
    path, count = normalize_csv(src)
    assert count == 1
    rows = read_repaired(path)
    assert rows[0][4] == "STRADA\nBIS"
    assert rows[0][5] == "LOC\nALITA"
    assert rows[0][6] == "39"


def test_carriage_returns_are_kept_as_data(tmp_path):
    clean = "H501;058091;1;;VIA\rROMA;;12;;;"
    src = tmp_path / "s.csv"
    src.write_bytes(f"{STRADARIO_HEADER}\n{clean}\n".encode())
    assert normalize_csv(src) == (src, 0)

    split = "B242;065017;2;;STRADA\r\nBIS\r;;39;;;"
    src.write_bytes(f"{STRADARIO_HEADER}\n{clean}\n{split}\n".encode())
    path, count = normalize_csv(src)
    assert count == 1
    rows = read_repaired(path)
    assert rows[0][4] == "VIA\rROMA"
    assert rows[1][4] == "STRADA\r\nBIS\r"


def test_blank_line_between_records_is_skipped(tmp_path):
    src = write(
        tmp_path / "s.csv", f"{STRADARIO_HEADER}\n{CLEAN_ROW}\n\n{CLEAN_ROW}\n"
    )
    assert normalize_csv(src) == (src, 0)
    assert not (tmp_path / "s.repaired.csv").exists()
    rows = duckdb.sql(
        "SELECT CODICE_COMUNE FROM read_csv(?, delim=';', header=true, "
        "all_varchar=true)",
        params=[str(src)],
    ).fetchall()
    assert rows == [("H501",), ("H501",)]


def test_blank_line_at_end_of_file_is_skipped(tmp_path):
    for tail in ("\n", "\r\n", "\n\n"):
        src = tmp_path / "s.csv"
        src.write_bytes(f"{STRADARIO_HEADER}\n{CLEAN_ROW}\n{tail}".encode())
        assert normalize_csv(src) == (src, 0)


def test_blank_line_inside_a_split_record_is_kept(tmp_path):
    record = "B242;065017;1;;STRADA\n\nBIS;;39;;;"
    src = write(tmp_path / "s.csv", f"{STRADARIO_HEADER}\n{record}\n")
    path, count = normalize_csv(src)
    assert count == 1
    assert read_repaired(path)[0][4] == "STRADA\n\nBIS"


def test_blank_line_before_a_split_record_is_skipped(tmp_path):
    src = write(
        tmp_path / "s.csv", f"{STRADARIO_HEADER}\n\n{SPLIT_ROW}\n"
    )
    path, count = normalize_csv(src)
    assert count == 1
    assert read_repaired(path)[0][0] == "B242"


def test_too_many_fields_fails(tmp_path):
    src = write(
        tmp_path / "s.csv",
        f"{STRADARIO_HEADER}\n{CLEAN_ROW}\n{CLEAN_ROW};extra\n",
    )
    with pytest.raises(ValueError, match="line 3"):
        normalize_csv(src)


def test_file_ending_mid_record_fails(tmp_path):
    src = write(tmp_path / "s.csv", f"{STRADARIO_HEADER}\n{CLEAN_ROW}\nB242;0650\n")
    with pytest.raises(ValueError, match="line 3"):
        normalize_csv(src)


CIVICI_KEYS = ["CODICE_ISTAT", "PROGRESSIVO_NAZIONALE", "PROGRESSIVO_ACCESSO"]
CIVICI_COLUMNS = [*CIVICI_KEYS, "ODONIMO", "CIVICO"]
CIVICI_KEYED_HEADER = ";".join(CIVICI_COLUMNS)


def civici_text(rows: list[str]) -> str:
    return CIVICI_KEYED_HEADER + "\n" + "".join(r + "\n" for r in rows)


def reference_raw_parquet(csv_path: Path, parquet_path: Path) -> None:
    """Copy of the SQL update_data.csv_to_raw_parquet ran before it delegated."""
    con = duckdb.connect()
    con.execute("SET memory_limit='4GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"""
        COPY (
            SELECT *
            FROM read_csv(
                '{csv_path}',
                delim=';', header=true, quote='', escape='', all_varchar=true
            )
            ORDER BY
                CODICE_ISTAT,
                TRY_CAST(PROGRESSIVO_NAZIONALE AS BIGINT),
                TRY_CAST(PROGRESSIVO_ACCESSO AS BIGINT)
        ) TO '{parquet_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    con.close()


def test_civici_bytes_match_the_current_pipeline(tmp_path):
    src = write(
        tmp_path / "c.csv",
        civici_text(
            [
                "058091;10;2;VIA \"ROMA\";1,5",
                "058091;2;1;;7",
                "001001;3;1;VIA DEL SOLE;",
                "058091;10;1;VIA ROMA;3A",
            ]
        ),
    )
    ours = tmp_path / "ours.parquet"
    ref = tmp_path / "ref.parquet"
    rows = csv_to_raw_parquet(src, ours, INDIRIZZARIO)
    reference_raw_parquet(src, ref)
    assert rows == 4
    assert ours.read_bytes() == ref.read_bytes()


def describe(path: Path) -> list[tuple[str, str]]:
    return [
        (name, kind)
        for name, kind, *_ in duckdb.sql(
            "DESCRIBE SELECT * FROM read_parquet(?)", params=[str(path)]
        ).fetchall()
    ]


def test_stradario_has_nine_text_columns_in_file_order(tmp_path):
    src = write(tmp_path / "s.csv", f"{STRADARIO_HEADER}\n{CLEAN_ROW}\n")
    out = tmp_path / "s.parquet"
    assert csv_to_raw_parquet(src, out, STRADARIO) == 1
    assert describe(out) == [
        (name, "VARCHAR")
        for name in [
            "CODICE_COMUNE",
            "CODICE_ISTAT",
            "PROGRESSIVO_NAZIONALE",
            "CODICE_COMUNALE",
            "ODONIMO",
            "LOCALITA'",
            "TOTALE_ACCESSI",
            "DIZIONE_LINGUA1",
            "DIZIONE_LINGUA2",
        ]
    ]


def test_stradario_non_empty_trailing_column_fails(tmp_path):
    src = write(
        tmp_path / "s.csv",
        f"{STRADARIO_HEADER}\n{CLEAN_ROW}\nH501;058091;2;;VIA X;;1;;;x\n",
    )
    with pytest.raises(ValueError, match="column9"):
        csv_to_raw_parquet(src, tmp_path / "s.parquet", STRADARIO)


def test_split_record_keeps_its_line_feed(tmp_path):
    strad = write(
        tmp_path / "s.csv", f"{STRADARIO_HEADER}\n{CLEAN_ROW}\n{SPLIT_ROW}\n"
    )
    out = tmp_path / "s.parquet"
    assert csv_to_raw_parquet(strad, out, STRADARIO) == 2
    odonimi = duckdb.sql(
        "SELECT ODONIMO FROM read_parquet(?) ORDER BY PROGRESSIVO_NAZIONALE::BIGINT",
        params=[str(out)],
    ).fetchall()
    assert odonimi[1][0].endswith("BIS\n")

    civici = write(
        tmp_path / "c.csv",
        civici_text(["058091;1;1;VIA ROMA;1", "058091;2;1;VIA\nNUOVA\n;2"]),
    )
    out = tmp_path / "c.parquet"
    assert csv_to_raw_parquet(civici, out, INDIRIZZARIO) == 2
    odonimi = duckdb.sql(
        "SELECT ODONIMO FROM read_parquet(?) ORDER BY PROGRESSIVO_NAZIONALE::BIGINT",
        params=[str(out)],
    ).fetchall()
    assert odonimi[1][0] == "VIA\nNUOVA\n"
    assert not (tmp_path / "c.repaired.csv").exists()
    assert not (tmp_path / "s.repaired.csv").exists()


def test_stradario_output_order_is_independent_of_csv_order(tmp_path):
    rows = [
        "H501;058091;10;;VIA A;;1;;;",
        "H501;058091;2;;VIA B;;1;;;",
        "A001;001001;5;;VIA C;;1;;;",
    ]
    a = write(tmp_path / "a.csv", f"{STRADARIO_HEADER}\n" + "\n".join(rows) + "\n")
    b = write(
        tmp_path / "b.csv",
        f"{STRADARIO_HEADER}\n" + "\n".join(reversed(rows)) + "\n",
    )
    csv_to_raw_parquet(a, tmp_path / "a.parquet", STRADARIO)
    csv_to_raw_parquet(b, tmp_path / "b.parquet", STRADARIO)
    assert (tmp_path / "a.parquet").read_bytes() == (tmp_path / "b.parquet").read_bytes()
    first = duckdb.sql(
        "SELECT PROGRESSIVO_NAZIONALE FROM read_parquet(?)",
        params=[str(tmp_path / "a.parquet")],
    ).fetchall()
    assert [r[0] for r in first] == ["5", "2", "10"]


def make_entry(date: str, origin: str, zip_info=None) -> dict:
    return {
        "date": date,
        "origin": origin,
        "note": "",
        "zip": zip_info,
        "parquet": {},
        "archived": "x",
    }


def test_third_party_entry_may_have_no_zip(tmp_path):
    index = tmp_path / "releases.json"
    append_release(index, make_entry("2026-11-02", "third-party"), STRADARIO)
    releases = json.loads(index.read_text())["releases"]
    assert releases[0]["zip"] is None
    assert latest_release_date(index) == "2026-11-02"


def test_original_entry_without_zip_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="zip"):
        append_release(
            tmp_path / "releases.json", make_entry("2026-11-02", "original"), STRADARIO
        )


def test_origin_must_belong_to_the_dataset(tmp_path):
    with pytest.raises(ValueError, match="origin"):
        append_release(
            tmp_path / "releases.json",
            make_entry("2026-11-02", "reconstructed", {}),
            STRADARIO,
        )


def test_latest_release_date_of_a_missing_or_empty_index(tmp_path):
    index = tmp_path / "releases.json"
    assert latest_release_date(index) is None
    index.write_text('{"releases": []}')
    assert latest_release_date(index) is None


def test_release_entry_without_zip(tmp_path):
    parquet = tmp_path / "p.parquet"
    parquet.write_bytes(b"x")
    entry = release_entry("2026-11-02", None, parquet, 1, "third-party", "n", "t")
    assert entry["zip"] is None
    assert entry["parquet"]["rows"] == 1


def zip_with(*members: tuple[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, text in members:
            zf.writestr(name, text)
    return buffer.getvalue()


def test_archive_zip_takes_the_date_from_the_csv_name(tmp_path):
    payload = zip_with(
        ("STRAD_ITA_20261102.csv", f"{STRADARIO_HEADER}\n{CLEAN_ROW}\n{SPLIT_ROW}\n")
    )
    date = archive_zip(STRADARIO, payload, tmp_path, "original", "Scarico.")
    assert date == "2026-11-02"
    release = tmp_path / "stradario" / "2026-11-02"
    assert (release / "stradarioItalia_20261102.zip").read_bytes() == payload
    assert (release / "STRAD_ITA_20261102.parquet").exists()
    assert sorted(p.suffix for p in release.iterdir()) == [".parquet", ".zip"]
    entry = json.loads((tmp_path / "stradario" / "releases.json").read_text())[
        "releases"
    ][0]
    assert entry["date"] == "2026-11-02"
    assert entry["origin"] == "original"
    assert entry["zip"]["name"] == "stradarioItalia_20261102.zip"
    assert entry["parquet"]["rows"] == 2
    assert entry["archived"].endswith("Z")


@pytest.mark.parametrize(
    "members",
    [
        [("readme.txt", "x")],
        [("STRAD_ITA_2026.csv", "x")],
        [
            ("STRAD_ITA_20261102.csv", "x"),
            ("STRAD_ITA_20261103.csv", "x"),
        ],
    ],
)
def test_archive_zip_rejects_a_zip_without_one_matching_csv(tmp_path, members):
    with pytest.raises(ValueError, match="STRAD_ITA"):
        archive_zip(STRADARIO, zip_with(*members), tmp_path, "original", "")
    assert not (tmp_path / "stradario" / "releases.json").exists()


def test_third_party_parquet_is_text_and_ordered(tmp_path):
    src = tmp_path / "ondata.parquet"
    duckdb.sql(
        "COPY (SELECT * FROM (VALUES "
        "('H501', '058091', 10::BIGINT, NULL, 'VIA A', NULL, 1::BIGINT, "
        "NULL, NULL, NULL), "
        "('B242', '065017', 1345847::BIGINT, NULL, 'VIA B', NULL, 39::BIGINT, "
        "NULL, NULL, NULL)"
        ") t(CODICE_COMUNE, CODICE_ISTAT, PROGRESSIVO_NAZIONALE, DUG, ODONIMO, "
        "\"LOCALITA'\", TOTALE_ACCESSI, column7, column8, column9)) "
        f"TO '{src}' (FORMAT PARQUET)"
    )
    date = archive_third_party_parquet(src, "2026-11-02", tmp_path, "Ondata.")
    assert date == "2026-11-02"
    out = tmp_path / "stradario" / "2026-11-02" / "STRAD_ITA_20261102.parquet"
    assert [kind for _, kind in describe(out)] == ["VARCHAR"] * 9
    assert [name for name, _ in describe(out)][-2:] == ["column7", "column8"]
    rows = duckdb.sql(
        "SELECT PROGRESSIVO_NAZIONALE FROM read_parquet(?)", params=[str(out)]
    ).fetchall()
    assert [r[0] for r in rows] == ["10", "1345847"]
    entry = json.loads((tmp_path / "stradario" / "releases.json").read_text())[
        "releases"
    ][0]
    assert entry["origin"] == "third-party"
    assert entry["zip"] is None
    assert entry["parquet"]["rows"] == 2


def test_third_party_parquet_with_a_filled_column9_fails(tmp_path):
    src = tmp_path / "ondata.parquet"
    duckdb.sql(
        "COPY (SELECT 'a' AS CODICE_ISTAT, 1 AS PROGRESSIVO_NAZIONALE, "
        f"'x' AS column9) TO '{src}' (FORMAT PARQUET)"
    )
    with pytest.raises(ValueError, match="column9"):
        archive_third_party_parquet(src, "2026-11-02", tmp_path, "")


STRAD_URL = STRADARIO.url


def stradario_zip(ymd: str) -> bytes:
    return zip_with(
        (f"STRAD_ITA_{ymd}.csv", f"{STRADARIO_HEADER}\n{CLEAN_ROW}\n")
    )


def seed_index(data_dir: Path, date: str) -> None:
    append_release(
        data_dir / "stradario" / "releases.json",
        make_entry(date, "third-party"),
        STRADARIO,
    )


def mock_tail(respx_mock, ymd: str):
    return respx_mock.get(STRAD_URL).mock(
        return_value=httpx.Response(
            206, content=f"junk STRAD_ITA_{ymd}.csv junk".encode()
        )
    )


def test_remote_release_date_reads_the_zip_tail(respx_mock):
    route = respx_mock.get(STRAD_URL).mock(
        return_value=httpx.Response(
            206, content=b"STRAD_ITA_20260101.csv x STRAD_ITA_20261102.csv x"
        )
    )
    result = remote_release_date(STRADARIO)
    assert (result.year, result.month, result.day) == (2026, 11, 2)
    assert result.tzinfo is not None
    assert route.calls[0].request.headers["Range"] == "bytes=-65536"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(403),
        httpx.ConnectError("refused"),
        httpx.Response(206, content=b"no date here"),
        httpx.Response(206, content=b"INDIR_ITA_20261102.csv"),
    ],
)
def test_remote_release_date_is_none_when_unreadable(respx_mock, response):
    if isinstance(response, Exception):
        respx_mock.get(STRAD_URL).mock(side_effect=response)
    else:
        respx_mock.get(STRAD_URL).mock(return_value=response)
    assert remote_release_date(STRADARIO) is None


def test_download_zip_returns_the_body(respx_mock):
    respx_mock.get(STRAD_URL).mock(return_value=httpx.Response(200, content=b"zip"))
    assert download_zip(STRADARIO) == b"zip"


def test_download_zip_retries_then_succeeds(respx_mock, monkeypatch):
    sleeps = []
    monkeypatch.setattr("anncsu_archive.time.sleep", sleeps.append)
    respx_mock.get(STRAD_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, content=b"zip")]
    )
    assert download_zip(STRADARIO) == b"zip"
    assert sleeps == [30]


def test_download_zip_gives_up_after_three_attempts(respx_mock, monkeypatch):
    monkeypatch.setattr("anncsu_archive.time.sleep", lambda s: None)
    route = respx_mock.get(STRAD_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(SystemExit, match="3 attempts"):
        download_zip(STRADARIO)
    assert route.call_count == 3


def test_up_to_date_stradario_is_not_downloaded(tmp_path, respx_mock):
    seed_index(tmp_path, "2026-11-02")
    route = mock_tail(respx_mock, "20261102")
    assert archive_latest(STRADARIO, tmp_path) is None
    assert route.call_count == 1  # the tail only, no download


def test_older_remote_release_is_ignored(tmp_path, respx_mock):
    seed_index(tmp_path, "2026-11-02")
    route = mock_tail(respx_mock, "20261005")
    assert archive_latest(STRADARIO, tmp_path) is None
    assert route.call_count == 1


def test_new_release_is_archived(tmp_path, respx_mock):
    seed_index(tmp_path, "2026-10-05")
    payload = stradario_zip("20261102")

    def respond(request):
        if "Range" in request.headers:
            return httpx.Response(206, content=payload[-100:])
        return httpx.Response(200, content=payload)

    respx_mock.get(STRAD_URL).mock(side_effect=respond)
    assert archive_latest(STRADARIO, tmp_path) == "2026-11-02"
    release = tmp_path / "stradario" / "2026-11-02"
    assert (release / "stradarioItalia_20261102.zip").read_bytes() == payload
    entries = json.loads((tmp_path / "stradario" / "releases.json").read_text())[
        "releases"
    ]
    assert [e["date"] for e in entries] == ["2026-10-05", "2026-11-02"]
    assert entries[-1]["origin"] == "original"
    assert entries[-1]["note"] == "Scarico dal portale ANNCSU."


def test_first_release_is_archived_into_an_empty_directory(tmp_path, respx_mock):
    payload = stradario_zip("20261102")
    respx_mock.get(STRAD_URL).mock(
        side_effect=lambda r: httpx.Response(
            206 if "Range" in r.headers else 200, content=payload
        )
    )
    assert archive_latest(STRADARIO, tmp_path) == "2026-11-02"


def test_unknown_remote_date_raises(tmp_path, respx_mock):
    route = respx_mock.get(STRAD_URL).mock(return_value=httpx.Response(403))
    with pytest.raises(RuntimeError, match="remote date"):
        archive_latest(STRADARIO, tmp_path)
    assert route.call_count == 1
    assert not (tmp_path / "stradario").exists()


def test_cli_archive_zip_writes_the_index(tmp_path):
    zip_path = tmp_path / "in.zip"
    zip_path.write_bytes(
        zip_with(("STRAD_ITA_20261102.csv", f"{STRADARIO_HEADER}\n{CLEAN_ROW}\n"))
    )
    data_dir = tmp_path / "data"
    result = CliRunner().invoke(
        app,
        [
            "archive-zip",
            "stradario",
            str(zip_path),
            "--note",
            "Prova.",
            "--data-dir",
            str(data_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    entry = json.loads((data_dir / "stradario" / "releases.json").read_text())[
        "releases"
    ][0]
    assert entry["date"] == "2026-11-02"
    assert entry["origin"] == "original"
    assert entry["note"] == "Prova."
    assert entry["parquet"]["rows"] == 1


def test_cli_archive_zip_rejects_an_unknown_dataset(tmp_path):
    zip_path = tmp_path / "in.zip"
    zip_path.write_bytes(b"")
    result = CliRunner().invoke(
        app,
        ["archive-zip", "civici", str(zip_path), "--note", "x",
         "--data-dir", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert not (tmp_path / "releases.json").exists()


def test_cli_third_party_requires_a_date(tmp_path):
    src = tmp_path / "ondata.parquet"
    src.write_bytes(b"")
    result = CliRunner().invoke(
        app,
        ["archive-third-party", str(src), "--note", "x",
         "--data-dir", str(tmp_path / "data")],
    )
    assert result.exit_code != 0
    assert not (tmp_path / "data").exists()


def test_cli_third_party_archives_a_parquet(tmp_path):
    src = tmp_path / "ondata.parquet"
    duckdb.sql(
        "COPY (SELECT * FROM (VALUES "
        "('H501', '058091', 10::BIGINT, NULL, 'VIA A', NULL, 1::BIGINT, "
        "NULL, NULL, NULL)"
        ") t(CODICE_COMUNE, CODICE_ISTAT, PROGRESSIVO_NAZIONALE, DUG, ODONIMO, "
        "\"LOCALITA'\", TOTALE_ACCESSI, column7, column8, column9)) "
        f"TO '{src}' (FORMAT PARQUET)"
    )
    data_dir = tmp_path / "data"
    result = CliRunner().invoke(
        app,
        ["archive-third-party", str(src), "--date", "2025-01-28",
         "--note", "Ondata.", "--data-dir", str(data_dir)],
    )
    assert result.exit_code == 0, result.output
    entry = json.loads((data_dir / "stradario" / "releases.json").read_text())[
        "releases"
    ][0]
    assert entry["date"] == "2025-01-28"
    assert entry["origin"] == "third-party"
    assert entry["zip"] is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
