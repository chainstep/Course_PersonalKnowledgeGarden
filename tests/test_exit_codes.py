from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run_cli(args: list[str], data_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "KG_DATA_DIR": str(data_dir), "KG_EMBED_BACKEND": "fake"}
    return subprocess.run(
        [sys.executable, "-m", "knowledge_garden.cli", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )


def test_domain_error_exits_3(tmp_path: Path):
    bad = tmp_path / "blob.bin"
    bad.write_bytes(b"\x00\x01")
    result = _run_cli(["add", str(bad)], tmp_path / "data")
    assert result.returncode == 3
    assert "unsupported file type" in result.stderr


def test_usage_error_exits_2(tmp_path: Path):
    result = _run_cli(["add"], tmp_path / "data")
    assert result.returncode == 2


def test_success_exits_0(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("# Title\n\nbody text")
    result = _run_cli(["add", str(note)], tmp_path / "data")
    assert result.returncode == 0
    assert "chunks=" in result.stdout


def test_reindex_quiet_flag(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("# Title\n\nbody text")
    data = tmp_path / "data"
    assert _run_cli(["add", str(note)], data).returncode == 0
    quiet = _run_cli(["reindex", "--json", "--quiet"], data)
    assert quiet.returncode == 0
    assert quiet.stdout.strip() == ""