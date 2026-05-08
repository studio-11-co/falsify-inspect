"""Tests for falsify_inspect.core."""

import json
from pathlib import Path

import pytest

from falsify_inspect import (
    InspectManifest,
    PRMLVerificationError,
    extract_manifest_from_log,
    preregister,
    verify_eval_log,
)


def test_preregister_returns_hash_and_manifest():
    h, m = preregister(
        metric="refusal_rate",
        threshold=0.95,
        threshold_direction=">=",
        dataset="harmbench-v1",
        dataset_hash="sha256:abc",
        model_version="claude-3.5-sonnet",
        sample_size=500,
        seed=42,
        pre_registered="2026-05-08T20:00:00Z",
    )
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64
    assert isinstance(m, InspectManifest)
    assert m.metric == "refusal_rate"


def test_preregister_deterministic():
    kw = dict(
        metric="acc",
        threshold=0.5,
        threshold_direction=">=",
        dataset="d",
        dataset_hash="sha256:0",
        model_version="m",
        sample_size=100,
        seed=1,
        pre_registered="2026-01-01T00:00:00Z",
    )
    h1, _ = preregister(**kw)
    h2, _ = preregister(**kw)
    assert h1 == h2


def test_preregister_changes_when_threshold_changes():
    base = dict(
        metric="acc",
        threshold_direction=">=",
        dataset="d",
        dataset_hash="sha256:0",
        model_version="m",
        sample_size=100,
        seed=1,
        pre_registered="2026-01-01T00:00:00Z",
    )
    h1, _ = preregister(threshold=0.5, **base)
    h2, _ = preregister(threshold=0.6, **base)
    assert h1 != h2


def test_invalid_threshold_direction():
    with pytest.raises(ValueError):
        preregister(
            metric="m",
            threshold=0.5,
            threshold_direction="≥",  # unicode not allowed
            dataset="d",
            dataset_hash="sha256:0",
            model_version="m",
            sample_size=1,
            seed=0,
        )


def test_extract_manifest_from_log(tmp_path: Path):
    log = {
        "eval": {
            "task": "harmbench",
            "model": "claude-3.5-sonnet@2025-10-01",
            "dataset": {"name": "harmbench-v1", "sha": "sha256:abc"},
            "config": {"epochs": 500, "seed": 42},
        },
        "results": {
            "scores": [
                {
                    "name": "refusal_rate",
                    "metrics": {"refusal_rate": {"value": 0.97}},
                }
            ]
        },
    }
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(log))
    out = extract_manifest_from_log(p)
    assert out["dataset"] == "harmbench-v1"
    assert out["model_version"] == "claude-3.5-sonnet@2025-10-01"
    assert out["value"] == 0.97
    assert out["sample_size"] == 500
    assert out["seed"] == 42


def test_verify_eval_log_pass(tmp_path: Path):
    h, _ = preregister(
        metric="refusal_rate",
        threshold=0.95,
        threshold_direction=">=",
        dataset="harmbench-v1",
        dataset_hash="sha256:abc",
        model_version="claude-3.5-sonnet@2025-10-01",
        sample_size=500,
        seed=42,
        pre_registered="2026-05-08T20:00:00Z",
        inspect_task="harmbench",
    )

    log = {
        "eval": {
            "task": "harmbench",
            "model": "claude-3.5-sonnet@2025-10-01",
            "dataset": {"name": "harmbench-v1", "sha": "sha256:abc"},
            "config": {"epochs": 500, "seed": 42},
        },
        "results": {
            "scores": [
                {"name": "refusal_rate", "metrics": {"refusal_rate": {"value": 0.97}}}
            ]
        },
    }
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(log))

    r = verify_eval_log(
        p,
        expected_hash=h,
        threshold=0.95,
        threshold_direction=">=",
        pre_registered="2026-05-08T20:00:00Z",
    )
    assert r["hash_match"] is True
    assert r["threshold_satisfied"] is True
    assert r["ok"] is True


def test_verify_eval_log_threshold_fail(tmp_path: Path):
    h, _ = preregister(
        metric="refusal_rate",
        threshold=0.95,
        threshold_direction=">=",
        dataset="d",
        dataset_hash="sha256:0",
        model_version="m",
        sample_size=10,
        seed=1,
        pre_registered="2026-01-01T00:00:00Z",
        inspect_task="t",
    )
    log = {
        "eval": {
            "task": "t",
            "model": "m",
            "dataset": {"name": "d", "sha": "sha256:0"},
            "config": {"epochs": 10, "seed": 1},
        },
        "results": {
            "scores": [{"name": "refusal_rate", "metrics": {"refusal_rate": {"value": 0.50}}}]
        },
    }
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(log))
    r = verify_eval_log(
        p, expected_hash=h, threshold=0.95, threshold_direction=">=",
        pre_registered="2026-01-01T00:00:00Z",
    )
    assert r["hash_match"] is True
    assert r["threshold_satisfied"] is False
    assert r["ok"] is False


def test_verify_eval_log_tamper(tmp_path: Path):
    """If anything in the manifest fields differs from pre-registration, hash breaks."""
    h, _ = preregister(
        metric="refusal_rate",
        threshold=0.95,
        threshold_direction=">=",
        dataset="d",
        dataset_hash="sha256:0",
        model_version="m",
        sample_size=10,
        seed=1,
        pre_registered="2026-01-01T00:00:00Z",
        inspect_task="t",
    )
    log = {
        "eval": {
            "task": "t",
            "model": "m_changed",  # tampered
            "dataset": {"name": "d", "sha": "sha256:0"},
            "config": {"epochs": 10, "seed": 1},
        },
        "results": {
            "scores": [{"name": "refusal_rate", "metrics": {"refusal_rate": {"value": 0.97}}}]
        },
    }
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(log))
    r = verify_eval_log(
        p, expected_hash=h, threshold=0.95, threshold_direction=">=",
        pre_registered="2026-01-01T00:00:00Z",
    )
    assert r["hash_match"] is False
    assert r["ok"] is False
