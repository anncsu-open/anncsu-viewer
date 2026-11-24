# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
# ]
# ///
"""Every script that uses DuckDB runs on the same version.

Usage:
    uv run scripts/test_dependencies.py

Each script carries its own PEP 723 header, so two of them can resolve
different DuckDB releases. In November 2026 the scripts that depend on
geoparquet-io, the tests among them, resolved 1.5.6 because geoparquet-io caps
DuckDB below 1.6, while build_catalog.py and generate_comuni_h3.py resolved
2.0.1 in production, a version their tests never ran on.

The pin is DuckDB 2.0.0 because the h3 community extension, which the pipeline
loads, is not yet published for 2.0.1. Scripts that depend on geoparquet-io
override its cap. Its stated reason is the S2 `geography` extension, which this
project does not use.
"""

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
DUCKDB_PIN = "duckdb==2.0.0"
GEOPARQUET_IO_FLOOR = "geoparquet-io>=1.8.0"

# The reference regex from PEP 723.
METADATA_BLOCK = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def tracked_scripts() -> list[Path]:
    """The Python scripts under version control.

    Untracked tools in scripts/ are deliberately left out of the repository,
    so they are left out of this check too.
    """
    listing = subprocess.run(
        ["git", "ls-files", "scripts/*.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO_ROOT / line for line in listing.stdout.split()]


def script_metadata(path: Path) -> dict:
    """The parsed PEP 723 `script` block, or an empty dict if there is none."""
    for match in METADATA_BLOCK.finditer(path.read_text(encoding="utf-8")):
        if match.group("type") != "script":
            continue
        content = "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in match.group("content").splitlines(keepends=True)
        )
        return tomllib.loads(content)
    return {}


def package_name(requirement: str) -> str:
    return re.split(r"[<>=!~ \[;]", requirement, maxsplit=1)[0].lower()


def scripts_depending_on(package: str) -> list[Path]:
    return [
        path
        for path in tracked_scripts()
        if any(
            package_name(requirement) == package
            for requirement in script_metadata(path).get("dependencies", [])
        )
    ]


@pytest.mark.parametrize(
    "script", scripts_depending_on("duckdb"), ids=lambda path: path.name
)
def test_pins_the_shared_duckdb_version(script):
    dependencies = script_metadata(script)["dependencies"]
    assert DUCKDB_PIN in dependencies, dependencies


@pytest.mark.parametrize(
    "script", scripts_depending_on("geoparquet-io"), ids=lambda path: path.name
)
def test_requires_a_geoparquet_io_that_runs_on_duckdb_2(script):
    dependencies = script_metadata(script)["dependencies"]
    assert GEOPARQUET_IO_FLOOR in dependencies, dependencies


@pytest.mark.parametrize(
    "script", scripts_depending_on("geoparquet-io"), ids=lambda path: path.name
)
def test_overrides_the_geoparquet_io_cap_with_the_same_pin(script):
    tool = script_metadata(script).get("tool", {}).get("uv", {})
    assert tool.get("override-dependencies") == [DUCKDB_PIN], tool


def test_finds_the_scripts_it_guards():
    """An empty parametrization would pass silently."""
    names = {path.name for path in scripts_depending_on("duckdb")}
    assert {"update_data.py", "build_catalog.py", "test_build_catalog.py"} <= names


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
