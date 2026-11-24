# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb==2.0.0",
#     "httpx",
#     "typer",
# ]
# ///
"""Shared code for archiving the ANNCSU stradario and civici files.

The portal CSVs use ";" as delimiter and no quoting. A few records carry a raw
line feed inside a text field, which splits them over several physical lines.
"""

import hashlib
import io
import json
import re
import time
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx
import typer

# Wraps fields that contain a line feed or a carriage return in the repaired
# CSV. No data value contains this character, so DuckDB can use it as both
# quote and escape character.
QUOTE = "\x01"

DELIMITER = ";"
# surrogateescape keeps undecodable bytes intact when the file is rewritten.
# newline="\n" splits lines on line feeds only, so a stray "\r" stays data and
# is written back unchanged.
ENCODING = {"encoding": "utf-8", "errors": "surrogateescape", "newline": "\n"}


def _records(csv_path: Path, expected: int) -> Iterator[tuple[int, list[str]]]:
    """Yield (starting line number, physical lines) for each record after the
    header. Raise ValueError for a record with too many fields or a file that
    ends inside a record."""
    with csv_path.open(**ENCODING) as handle:
        next(handle)
        lines: list[str] = []
        start = 0
        fields = 0
        for number, line in enumerate(handle, start=2):
            line = line.rstrip("\n")
            if not lines:
                # DuckDB skips a blank line between records. Inside an open
                # record it is part of the value, so only skip it here.
                if line in ("", "\r"):
                    continue
                start = number
            lines.append(line)
            fields += line.count(DELIMITER) + (0 if len(lines) > 1 else 1)
            if fields > expected:
                raise ValueError(
                    f"{csv_path.name}: record at line {start} has more than "
                    f"{expected} fields"
                )
            if fields == expected:
                yield start, lines
                lines, fields = [], 0
        if lines:
            raise ValueError(
                f"{csv_path.name}: file ends inside the record at line {start}"
            )


def normalize_csv(csv_path: Path) -> tuple[Path, int]:
    """Rejoin records split by a raw line feed inside a field.

    The expected field count comes from the header. Returns the path to read
    and the number of repaired records. A clean file is returned as is and
    nothing is written. Otherwise the repaired copy goes to
    `<stem>.repaired.csv` next to the source, with every field that contains
    a line feed or carriage return wrapped in QUOTE, so DuckDB does not take a
    stray "\\r" for a record break.
    """
    with csv_path.open(**ENCODING) as handle:
        header = handle.readline().rstrip("\n")
    expected = header.count(DELIMITER) + 1

    repaired = sum(1 for _, lines in _records(csv_path, expected) if len(lines) > 1)
    if repaired == 0:
        return csv_path, 0

    target = csv_path.with_name(f"{csv_path.stem}.repaired.csv")
    with target.open("w", **ENCODING) as out:
        out.write(header + "\n")
        for _, lines in _records(csv_path, expected):
            record = "\n".join(lines)
            if len(lines) == 1 and "\r" not in record:
                out.write(record + "\n")
                continue
            fields = record.split(DELIMITER)
            out.write(
                DELIMITER.join(
                    f"{QUOTE}{f}{QUOTE}" if "\n" in f or "\r" in f else f
                    for f in fields
                )
                + "\n"
            )
    return target, repaired


@dataclass(frozen=True)
class Dataset:
    """What differs between the two portal files.

    `order_by` holds the SQL expressions that fix the row order of the raw
    Parquet. `trailing_empty_column` marks a file whose header ends in
    separators with no name: DuckDB reads the last one as `column9`, which
    carries no data and is dropped.
    """

    key: str
    url: str
    csv_prefix: str
    zip_prefix: str
    order_by: tuple[str, ...]
    origins: tuple[str, ...]
    trailing_empty_column: bool
    subdir: str


_PORTAL = "https://anncsu.open.agenziaentrate.gov.it/age-inspire/opendata/anncsu"

INDIRIZZARIO = Dataset(
    "indirizzario",
    f"{_PORTAL}/getds.php?INDIR_ITA",
    "INDIR_ITA",
    "indirizzarioItalia",
    (
        "CODICE_ISTAT",
        "TRY_CAST(PROGRESSIVO_NAZIONALE AS BIGINT)",
        "TRY_CAST(PROGRESSIVO_ACCESSO AS BIGINT)",
    ),
    ("original", "reconstructed"),
    False,
    "rilasci",
)

STRADARIO = Dataset(
    "stradario",
    f"{_PORTAL}/getds.php?STRAD_ITA",
    "STRAD_ITA",
    "stradarioItalia",
    ("CODICE_ISTAT", "TRY_CAST(PROGRESSIVO_NAZIONALE AS BIGINT)"),
    ("original", "third-party"),
    True,
    "stradario",
)

TRAILING_COLUMN = "column9"


def _sql_literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def csv_to_raw_parquet(csv_path: Path, parquet_path: Path, dataset: Dataset) -> int:
    """Convert a raw ANNCSU CSV to Parquet without losing anything.

    Every column stays text exactly as the portal writes it: Italian decimal
    commas, leading-zero codes, quotes inside odonyms. Empty fields become
    NULL, which is what they mean in the CSV. Records split by a raw line feed
    are rejoined first and keep that line feed in the value. Rows are ordered
    by the dataset's identifying columns so the output does not depend on the
    CSV's order, which the portal does not fix and a reconstruction cannot
    reproduce. Returns the row count.
    """
    read_path, repaired = normalize_csv(csv_path)
    con = duckdb.connect()
    try:
        # Bounded like enhance_parquet: the sort spills to disk instead of
        # OOMing the runner. ORDER BY still fixes the output order.
        con.execute("SET memory_limit='4GB'")
        con.execute("SET preserve_insertion_order=false")
        source = (
            f"read_csv({_sql_literal(read_path)}, delim=';', header=true, "
            f"quote={_sql_literal(QUOTE)}, escape={_sql_literal(QUOTE)}, "
            "all_varchar=true)"
        )
        select = "*"
        if dataset.trailing_empty_column:
            filled = con.execute(
                f"SELECT count({TRAILING_COLUMN}) FROM {source}"
            ).fetchone()[0]
            if filled:
                raise ValueError(
                    f"{csv_path.name}: {filled} rows have a value in "
                    f"{TRAILING_COLUMN}, which should be empty"
                )
            select = f"* EXCLUDE ({TRAILING_COLUMN})"
        con.execute(
            f"COPY (SELECT {select} FROM {source} "
            f"ORDER BY {', '.join(dataset.order_by)}) "
            f"TO {_sql_literal(parquet_path)} (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        return con.execute(
            f"SELECT count(*) FROM read_parquet({_sql_literal(parquet_path)})"
        ).fetchone()[0]
    finally:
        con.close()
        if repaired:
            read_path.unlink(missing_ok=True)


def sha256_of(path: Path) -> str:
    """Plain hex sha256 of a file. The catalog adds the multihash prefix."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_entry(
    date: str,
    zip_path: Path | None,
    parquet_path: Path,
    rows: int,
    origin: str,
    note: str,
    archived: str,
) -> dict:
    """One entry of releases.json. `zip` is None when there is no ZIP."""
    return {
        "date": date,
        "origin": origin,
        "note": note,
        "zip": None
        if zip_path is None
        else {
            "name": zip_path.name,
            "size": zip_path.stat().st_size,
            "sha256": sha256_of(zip_path),
        },
        "parquet": {
            "name": parquet_path.name,
            "size": parquet_path.stat().st_size,
            "sha256": sha256_of(parquet_path),
            "rows": rows,
        },
        "archived": archived,
    }


def _read_releases(index_path: Path) -> list[dict]:
    if not index_path.exists():
        return []
    return json.loads(index_path.read_text(encoding="utf-8")).get("releases", [])


def append_release(index_path: Path, entry: dict, dataset: Dataset) -> None:
    """Add or replace the entry for one date, keeping the index sorted.

    The origin must be one of the dataset's. Only a third-party release may
    have no ZIP.
    """
    if entry.get("origin") not in dataset.origins:
        raise ValueError(
            f"origin must be one of {dataset.origins}, got {entry.get('origin')!r}"
        )
    if entry.get("zip") is None and entry["origin"] != "third-party":
        raise ValueError(f"a {entry['origin']} release needs a zip entry")
    releases = [r for r in _read_releases(index_path) if r["date"] != entry["date"]]
    releases.append(entry)
    releases.sort(key=lambda r: r["date"])
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps({"releases": releases}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def latest_release_date(index_path: Path) -> str | None:
    """Date of the newest release in the index, or None if there is none."""
    releases = _read_releases(index_path)
    return max((r["date"] for r in releases), default=None)


def _now() -> str:
    # The only wall-clock value in the pipeline. Written once into the index
    # and never recomputed, so the catalog generator stays deterministic.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def archive_zip(
    dataset: Dataset, zip_bytes: bytes, data_dir: Path, origin: str, note: str
) -> str:
    """Archive a portal ZIP: the ZIP as given, the raw Parquet and an index entry.

    The release date comes from the name of the one CSV in the ZIP,
    `<csv_prefix>_<yyyymmdd>.csv`. Files go to `data_dir/<subdir>/<date>/` and
    the entry to `data_dir/<subdir>/releases.json`. The extracted CSV is
    deleted after the conversion. Returns the date as `yyyy-mm-dd`.
    """
    pattern = re.compile(rf"{re.escape(dataset.csv_prefix)}_(\d{{8}})\.csv")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = [n for n in zf.namelist() if pattern.fullmatch(n)]
        if len(names) != 1:
            raise ValueError(
                f"expected one {dataset.csv_prefix}_<yyyymmdd>.csv in the ZIP, "
                f"found {len(names)}: {zf.namelist()}"
            )
        csv_name = names[0]
        ymd = pattern.fullmatch(csv_name).group(1)
        date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"

        subdir = data_dir / dataset.subdir
        release_dir = subdir / date
        release_dir.mkdir(parents=True, exist_ok=True)
        zip_path = release_dir / f"{dataset.zip_prefix}_{ymd}.zip"
        zip_path.write_bytes(zip_bytes)

        csv_path = release_dir / csv_name
        parquet_path = release_dir / f"{dataset.csv_prefix}_{ymd}.parquet"
        try:
            with zf.open(csv_name) as src, csv_path.open("wb") as out:
                while chunk := src.read(1024 * 1024):
                    out.write(chunk)
            rows = csv_to_raw_parquet(csv_path, parquet_path, dataset)
        finally:
            csv_path.unlink(missing_ok=True)
            csv_path.with_name(f"{csv_path.stem}.repaired.csv").unlink(
                missing_ok=True
            )

    append_release(
        subdir / "releases.json",
        release_entry(date, zip_path, parquet_path, rows, origin, note, _now()),
        dataset,
    )
    return date


def archive_third_party_parquet(
    src: Path, date: str, data_dir: Path, note: str
) -> str:
    """Archive a stradario Parquet published by a third party (no ZIP).

    The source has typed columns. Every column is cast to text, so the output
    matches the raw Parquet of the portal CSV: same `column9` rule, same order,
    columns in file order. Returns the date.
    """
    dataset = STRADARIO
    ymd = date.replace("-", "")
    release_dir = data_dir / dataset.subdir / date
    release_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = release_dir / f"{dataset.csv_prefix}_{ymd}.parquet"

    source = f"read_parquet({_sql_literal(src)})"
    con = duckdb.connect()
    try:
        con.execute("SET memory_limit='4GB'")
        con.execute("SET preserve_insertion_order=false")
        columns = [
            row[0]
            for row in con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()
        ]
        if TRAILING_COLUMN in columns:
            filled = con.execute(
                f"SELECT count(*) FROM {source} WHERE "
                f"{TRAILING_COLUMN} IS NOT NULL AND CAST({TRAILING_COLUMN} AS "
                "VARCHAR) <> ''"
            ).fetchone()[0]
            if filled:
                raise ValueError(
                    f"{src.name}: {filled} rows have a value in "
                    f"{TRAILING_COLUMN}, which should be empty"
                )
        casts = ", ".join(
            f'CAST("{c}" AS VARCHAR) AS "{c}"' for c in columns if c != TRAILING_COLUMN
        )
        con.execute(
            f"COPY (SELECT * FROM (SELECT {casts} FROM {source}) "
            f"ORDER BY {', '.join(dataset.order_by)}) "
            f"TO {_sql_literal(parquet_path)} (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        rows = con.execute(
            f"SELECT count(*) FROM read_parquet({_sql_literal(parquet_path)})"
        ).fetchone()[0]
    finally:
        con.close()

    append_release(
        data_dir / dataset.subdir / "releases.json",
        release_entry(date, None, parquet_path, rows, "third-party", note, _now()),
        dataset,
    )
    return date


TAIL_SIZE = 65536
DOWNLOAD_TIMEOUT = 600
MAX_RETRIES = 3
RETRY_WAIT = 30


def remote_release_date(dataset: Dataset) -> datetime | None:
    """Date of the release on the portal, read from the tail of the ZIP.

    The CSV name sits in the ZIP's central directory at the end of the file,
    so a Range request for the last bytes is enough. Returns None, with a
    warning, if the request fails or the tail has no CSV name.
    """
    print(f"Checking the remote {dataset.key} date ...")
    try:
        response = httpx.get(
            dataset.url,
            headers={"Range": f"bytes=-{TAIL_SIZE}"},
            follow_redirects=True,
            timeout=60,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print(f"Warning: could not fetch remote date (HTTP {exc.response.status_code})")
        return None
    except httpx.TransportError as exc:
        print(f"Warning: could not fetch remote date ({exc})")
        return None

    pattern = rf"{re.escape(dataset.csv_prefix)}_(\d{{8}})\.csv".encode()
    matches = re.findall(pattern, response.content)
    if not matches:
        print("Warning: no release date found in the remote ZIP tail")
        return None
    remote_date = datetime.strptime(matches[-1].decode(), "%Y%m%d").replace(
        tzinfo=timezone.utc
    )
    print(f"Remote {dataset.key} date: {remote_date.date()}")
    return remote_date


def download_zip(dataset: Dataset) -> bytes:
    """Download the portal ZIP, retrying on HTTP and transport errors.

    The portal serves only the latest release, so the bytes are kept exactly
    as received. Raises SystemExit after `MAX_RETRIES` failed attempts.
    """
    print(f"Downloading from {dataset.url} ...")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = io.BytesIO()
            with httpx.stream(
                "GET", dataset.url, follow_redirects=True, timeout=DOWNLOAD_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                    data.write(chunk)
            break
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            if attempt == MAX_RETRIES:
                raise SystemExit(
                    f"Download failed after {MAX_RETRIES} attempts: {exc}"
                ) from exc
            print(
                f"Attempt {attempt}/{MAX_RETRIES} failed ({exc}), "
                f"retrying in {RETRY_WAIT}s ..."
            )
            time.sleep(RETRY_WAIT)
    size = data.getbuffer().nbytes
    print(f"Downloaded {size / (1024 * 1024):.1f} MB")
    return data.getvalue()


def archive_latest(dataset: Dataset, data_dir: Path) -> str | None:
    """Archive the portal's current release unless the index already has it.

    Returns the archived date, or None when the index holds that date or a
    later one. An unreadable remote date is an error: this path never
    downloads blind.
    """
    remote = remote_release_date(dataset)
    if remote is None:
        raise RuntimeError(
            f"could not read the remote date of the {dataset.key}; "
            "not downloading blind"
        )
    remote_date = remote.strftime("%Y-%m-%d")
    latest = latest_release_date(data_dir / dataset.subdir / "releases.json")
    if latest is not None and latest >= remote_date:
        print(f"The {dataset.key} is up to date ({latest}).")
        return None
    date = archive_zip(
        dataset,
        download_zip(dataset),
        data_dir,
        "original",
        "Scarico dal portale ANNCSU.",
    )
    print(f"Archived the {dataset.key} release {date}.")
    return date


DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATASETS = {d.key: d for d in (INDIRIZZARIO, STRADARIO)}

app = typer.Typer(add_completion=False, help="Archive ANNCSU releases.")


@app.command("archive-zip")
def archive_zip_command(
    dataset: str = typer.Argument(..., help="indirizzario or stradario"),
    zip_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    note: str = typer.Option(..., "--note", help="Where the ZIP comes from."),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir"),
) -> None:
    """Archive a portal ZIP as an original release."""
    if dataset not in DATASETS:
        raise typer.BadParameter(
            f"expected one of {', '.join(DATASETS)}", param_hint="DATASET"
        )
    date = archive_zip(
        DATASETS[dataset], zip_path.read_bytes(), data_dir, "original", note
    )
    print(f"Archived the {dataset} release {date}.")


@app.command("archive-third-party")
def archive_third_party_command(
    parquet_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    date: str = typer.Option(
        ..., "--date", help="Release date, YYYY-MM-DD."
    ),
    note: str = typer.Option(..., "--note", help="Where the Parquet comes from."),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir"),
) -> None:
    """Archive a stradario Parquet published by a third party."""
    archived = archive_third_party_parquet(parquet_path, date, data_dir, note)
    print(f"Archived the stradario release {archived} (third party).")


if __name__ == "__main__":
    app()
