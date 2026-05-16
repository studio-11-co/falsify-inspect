"""Tests for falsify_inspect.cli."""

from argparse import Namespace
from pathlib import Path

from falsify_inspect.cli import _cmd_verify


def test_cmd_verify_malformed_json_exits_2(tmp_path: Path, capsys):
    log_path = tmp_path / "broken.log"
    log_path.write_text("not valid json", encoding="utf-8")

    exit_code = _cmd_verify(
        Namespace(
            log=log_path,
            hash="deadbeef",
            threshold=0.95,
            threshold_direction=">=",
            pre_registered="2026-05-08T20:00:00Z",
            sample_size=None,
            seed=None,
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "structurally invalid log: malformed JSON" in captured.err
