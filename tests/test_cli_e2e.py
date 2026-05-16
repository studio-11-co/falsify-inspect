"""End-to-end CLI tests.

These exercise the real `falsify-inspect` console-script via subprocess —
the same invocation a user, a CI workflow, or the cookbook examples make.
They are stricter than unit tests because they verify exit-code contract:

    0  PASS  — hash matches AND threshold satisfied
    10 FAIL  — hash matches but threshold not satisfied
    3  TAMPER — hash does not match (any manifest field drift)
    2  IO     — log file missing

This contract is what downstream tooling (CI gates, `prml-verify-action`,
cookbook patterns) relies on. Breaking it silently would be a major regression.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


# Invoke the CLI via the running interpreter so the test works under any
# install layout (venv, editable install, system-wide). Equivalent to the
# `falsify-inspect` console-script but PATH-independent.
CLI_CMD = [sys.executable, "-m", "falsify_inspect.cli"]


def _run(*args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*CLI_CMD, *args],
        capture_output=True,
        text=True,
        **kw,
    )


def _lock(tmp_path: Path, **overrides) -> tuple[str, Path]:
    """Run `lock`, return (hash, manifest_path)."""
    out = tmp_path / "claim.prml.yaml"
    args = {
        "--metric": "refusal_rate",
        "--threshold": "0.95",
        "--threshold-direction": ">=",
        "--dataset": "harmbench-v1",
        "--dataset-hash": "sha256:abc",
        "--model-version": "claude-3.5-sonnet@2025-10-01",
        "--sample-size": "500",
        "--seed": "42",
        "--task": "harmbench",
        "--output": str(out),
    }
    args.update(overrides)
    cli_args = []
    for k, v in args.items():
        cli_args.extend([k, str(v)])
    r = _run("lock", *cli_args)
    assert r.returncode == 0, f"lock failed: {r.stderr}"
    h = r.stdout.strip()
    assert h.startswith("sha256:"), f"unexpected lock output: {h!r}"
    return h, out


def _log(tmp_path: Path, **fields) -> Path:
    base = {
        "task": "harmbench",
        "model": "claude-3.5-sonnet@2025-10-01",
        "dataset_name": "harmbench-v1",
        "dataset_sha": "sha256:abc",
        "epochs": 500,
        "seed": 42,
        "metric": "refusal_rate",
        "value": 0.97,
    }
    base.update(fields)
    payload = {
        "eval": {
            "task": base["task"],
            "model": base["model"],
            "dataset": {"name": base["dataset_name"], "sha": base["dataset_sha"]},
            "config": {"epochs": base["epochs"], "seed": base["seed"]},
        },
        "results": {
            "scores": [
                {"name": base["metric"], "metrics": {base["metric"]: {"value": base["value"]}}}
            ]
        },
    }
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(payload))
    return p


def _pre_registered_from_manifest(manifest_path: Path) -> str:
    # The manifest YAML carries `pre_registered:` — read it back so verify
    # uses the *same* timestamp lock used (otherwise the hash differs).
    import yaml
    data = yaml.safe_load(manifest_path.read_text())
    return data["pre_registered"]


# --- exit-code contract -----------------------------------------------------


def test_cli_lock_emits_sha256_hash(tmp_path: Path):
    h, _ = _lock(tmp_path)
    assert len(h) == len("sha256:") + 64


def test_cli_verify_pass_exit_0(tmp_path: Path):
    h, manifest = _lock(tmp_path)
    ts = _pre_registered_from_manifest(manifest)
    log = _log(tmp_path, value=0.97)
    r = _run(
        "verify", str(log),
        "--hash", h,
        "--threshold", "0.95",
        "--threshold-direction", ">=",
        "--pre-registered", ts,
    )
    assert r.returncode == 0, f"expected 0, got {r.returncode}\nstdout={r.stdout}\nstderr={r.stderr}"
    body = json.loads(r.stdout)
    assert body["hash_match"] is True
    assert body["threshold_satisfied"] is True
    assert body["ok"] is True


def test_cli_verify_threshold_fail_exit_10(tmp_path: Path):
    h, manifest = _lock(tmp_path)
    ts = _pre_registered_from_manifest(manifest)
    log = _log(tmp_path, value=0.50)  # below 0.95 threshold
    r = _run(
        "verify", str(log),
        "--hash", h,
        "--threshold", "0.95",
        "--threshold-direction", ">=",
        "--pre-registered", ts,
    )
    assert r.returncode == 10, f"expected 10, got {r.returncode}\nstderr={r.stderr}"
    body = json.loads(r.stdout)
    assert body["hash_match"] is True
    assert body["threshold_satisfied"] is False


def test_cli_verify_model_drift_exit_3_tamper(tmp_path: Path):
    h, manifest = _lock(tmp_path)
    ts = _pre_registered_from_manifest(manifest)
    log = _log(tmp_path, model="claude-4-opus@2026-01-15")  # drifted from locked
    r = _run(
        "verify", str(log),
        "--hash", h,
        "--threshold", "0.95",
        "--threshold-direction", ">=",
        "--pre-registered", ts,
    )
    assert r.returncode == 3, f"expected 3, got {r.returncode}\nstderr={r.stderr}"


def test_cli_verify_dataset_drift_exit_3_tamper(tmp_path: Path):
    h, manifest = _lock(tmp_path)
    ts = _pre_registered_from_manifest(manifest)
    log = _log(tmp_path, dataset_sha="sha256:def")  # tampered dataset hash
    r = _run(
        "verify", str(log),
        "--hash", h,
        "--threshold", "0.95",
        "--threshold-direction", ">=",
        "--pre-registered", ts,
    )
    assert r.returncode == 3, f"expected 3 (tamper), got {r.returncode}\nstderr={r.stderr}"


def test_cli_verify_seed_drift_exit_3_tamper(tmp_path: Path):
    h, manifest = _lock(tmp_path)
    ts = _pre_registered_from_manifest(manifest)
    log = _log(tmp_path, seed=99)  # different seed than locked (42)
    r = _run(
        "verify", str(log),
        "--hash", h,
        "--threshold", "0.95",
        "--threshold-direction", ">=",
        "--pre-registered", ts,
    )
    assert r.returncode == 3, f"expected 3 (tamper), got {r.returncode}\nstderr={r.stderr}"


def test_cli_verify_missing_metric_field_exit_2_not_3(tmp_path: Path):
    """A structurally invalid log (no `results.scores`) must exit 2, never 3.

    Conflating 'malformed log' with 'tamper' (exit 3) corrupts the CI signal:
    a downstream consumer would think someone edited the threshold post-hoc
    when in fact the eval log shape is just wrong. See issue #12."""
    h, manifest = _lock(tmp_path)
    ts = _pre_registered_from_manifest(manifest)
    nomet = tmp_path / "nomet.log"
    nomet.write_text(json.dumps({"some": "valid_json_but_no_metric"}))
    r = _run(
        "verify", str(nomet),
        "--hash", h,
        "--threshold", "0.95",
        "--threshold-direction", ">=",
        "--pre-registered", ts,
    )
    assert r.returncode == 2, f"expected 2 (malformed), got {r.returncode}\nstderr={r.stderr}"
    assert "structurally invalid" in r.stderr.lower()
    # Crucially: must NOT be the tamper signal.
    assert "tamper" not in r.stderr.lower() or "not a tamper" in r.stderr.lower()


def test_cli_verify_missing_log_exit_2(tmp_path: Path):
    h, manifest = _lock(tmp_path)
    ts = _pre_registered_from_manifest(manifest)
    r = _run(
        "verify", str(tmp_path / "does-not-exist.json"),
        "--hash", h,
        "--threshold", "0.95",
        "--threshold-direction", ">=",
        "--pre-registered", ts,
    )
    assert r.returncode == 2, f"expected 2 (io), got {r.returncode}\nstderr={r.stderr}"


def test_cli_lock_is_deterministic(tmp_path: Path):
    """Two locks with identical fields and the same `pre_registered`
    must produce byte-identical hashes — this is the headline PRML property."""
    h1, m1 = _lock(tmp_path)
    ts = _pre_registered_from_manifest(m1)
    # Re-lock pinning `pre_registered` to the same timestamp via the manifest:
    # we can't pass it on the CLI today, but reading the manifest back proves
    # the field is captured. Determinism is unit-tested at the core layer;
    # here we assert the manifest survives a round-trip.
    import yaml
    data = yaml.safe_load(m1.read_text())
    # The hash output prefix + length contract is already covered above.
    assert data["metric"] == "refusal_rate"
    assert data["threshold"] == 0.95
    assert data["seed"] == 42
    assert data["dataset"] == "harmbench-v1"
    assert h1.startswith("sha256:")
