"""Tests for falsify_inspect.cli."""

import subprocess
import sys
from pathlib import Path


def test_verify_malformed_json_exits_2_without_traceback(tmp_path: Path):
    log_path = tmp_path / "broken.log"
    log_path.write_text("not valid json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "falsify_inspect.cli",
            "verify",
            str(log_path),
            "--hash",
            "deadbeef",
            "--threshold",
            "0.5",
            "--threshold-direction",
            ">=",
            "--pre-registered",
            "2026-01-01T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "structurally invalid log:" in result.stderr
    assert "Traceback" not in result.stderr
