"""Tests for falsify_inspect.core (real PRML v0.1 schema, via falsify_prml)."""

import json
from pathlib import Path

import falsify_prml as prml
import pytest

from falsify_inspect import (
    InspectManifest,
    extract_manifest_from_log,
    preregister,
    verify_eval_log,
)
from falsify_inspect.core import MalformedLogError

# A valid PRML dataset.hash: 64 lowercase hex chars.
HEX = "a" * 64
HEX2 = "b" * 64


def test_preregister_returns_hash_and_manifest():
    h, m = preregister(
        metric="refusal_rate",
        threshold=0.95,
        threshold_direction=">=",
        dataset="harmbench-v1",
        dataset_hash=HEX,
        model_version="claude-3.5-sonnet",
        sample_size=500,
        seed=42,
        pre_registered="2026-05-08T20:00:00Z",
    )
    # Bare 64-hex canonical PRML hash (no "sha256:" prefix).
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
    assert isinstance(m, InspectManifest)
    assert m.metric == "refusal_rate"
    assert m.comparator == ">="


def test_preregister_matches_falsify_prml():
    """The adapter's hash must equal falsify_prml.manifest_hash of the manifest."""
    h, m = preregister(
        metric="acc",
        threshold=0.5,
        threshold_direction=">=",
        dataset="d",
        dataset_hash=HEX,
        model_version="m",
        seed=1,
        pre_registered="2026-01-01T00:00:00Z",
    )
    assert h == prml.manifest_hash(m.to_dict())
    assert prml.validate_manifest(m.to_dict()) == []


def test_preregister_deterministic():
    kw = dict(
        metric="acc",
        threshold=0.5,
        threshold_direction=">=",
        dataset="d",
        dataset_hash=HEX,
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
        dataset_hash=HEX,
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
            dataset_hash=HEX,
            model_version="m",
            sample_size=1,
            seed=0,
        )


def test_invalid_dataset_hash_rejected():
    """A non-hex dataset hash must be rejected by falsify_prml validation."""
    with pytest.raises(ValueError):
        preregister(
            metric="m",
            threshold=0.5,
            threshold_direction=">=",
            dataset="d",
            dataset_hash="sha256:not-hex",
            model_version="m",
            seed=0,
        )


def test_extract_manifest_from_log(tmp_path: Path):
    log = {
        "eval": {
            "task": "harmbench",
            "model": "claude-3.5-sonnet@2025-10-01",
            "dataset": {"name": "harmbench-v1", "sha": HEX},
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
    assert out["dataset_id"] == "harmbench-v1"
    assert out["producer_id"] == "claude-3.5-sonnet@2025-10-01"
    assert out["value"] == 0.97
    assert out["sample_size"] == 500
    assert out["seed"] == 42


def _matching_log(tmp_path: Path, *, value: float, model="claude-3.5-sonnet@2025-10-01",
                  dataset="harmbench-v1", sha=HEX, seed=42, epochs=500, task="harmbench") -> Path:
    log = {
        "eval": {
            "task": task,
            "model": model,
            "dataset": {"name": dataset, "sha": sha},
            "config": {"epochs": epochs, "seed": seed},
        },
        "results": {
            "scores": [
                {"name": "refusal_rate", "metrics": {"refusal_rate": {"value": value}}}
            ]
        },
    }
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(log))
    return p


def test_verify_eval_log_pass(tmp_path: Path):
    h, _ = preregister(
        metric="refusal_rate",
        threshold=0.95,
        threshold_direction=">=",
        dataset="harmbench-v1",
        dataset_hash=HEX,
        model_version="claude-3.5-sonnet@2025-10-01",
        sample_size=500,
        seed=42,
        pre_registered="2026-05-08T20:00:00Z",
        inspect_task="harmbench",
    )
    p = _matching_log(tmp_path, value=0.97)
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
        dataset_hash=HEX,
        model_version="m",
        sample_size=10,
        seed=1,
        pre_registered="2026-01-01T00:00:00Z",
        inspect_task="t",
    )
    p = _matching_log(
        tmp_path, value=0.50, model="m", dataset="d", sha=HEX, seed=1, epochs=10, task="t"
    )
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
        dataset_hash=HEX,
        model_version="m",
        sample_size=10,
        seed=1,
        pre_registered="2026-01-01T00:00:00Z",
        inspect_task="t",
    )
    p = _matching_log(
        tmp_path, value=0.97, model="m_changed", dataset="d", sha=HEX, seed=1, epochs=10, task="t"
    )
    r = verify_eval_log(
        p, expected_hash=h, threshold=0.95, threshold_direction=">=",
        pre_registered="2026-01-01T00:00:00Z",
    )
    assert r["hash_match"] is False
    assert r["ok"] is False


def _log_no_sha(tmp_path: Path, *, value: float, model="m", dataset="d", seed=1,
                epochs=10, task="t", scorer="match") -> Path:
    """A log shaped like CURRENT Inspect (0.3.x): no dataset.sha, and the scorer
    name -- not the metric -- in results.scores[].name."""
    log = {
        "eval": {
            "task": task,
            "model": model,
            "dataset": {"name": dataset},  # note: no "sha"
            "config": {"epochs": epochs, "seed": seed},
        },
        "results": {"scores": [{"name": scorer, "metrics": {"accuracy": {"value": value}}}]},
    }
    p = tmp_path / "eval_nosha.json"
    p.write_text(json.dumps(log))
    return p


def test_verify_eval_log_dataset_hash_and_metric_override(tmp_path: Path):
    """Current Inspect logs omit dataset.sha and carry the scorer name, not the
    metric. Supplying dataset_hash= and metric= reconstructs the locked manifest."""
    h, _ = preregister(
        metric="accuracy", threshold=0.75, threshold_direction=">=",
        dataset="d", dataset_hash=HEX, model_version="m", sample_size=10, seed=1,
        pre_registered="2026-01-01T00:00:00Z", inspect_task="t",
    )
    p = _log_no_sha(tmp_path, value=0.80, scorer="match")
    r = verify_eval_log(
        p, expected_hash=h, threshold=0.75, threshold_direction=">=",
        pre_registered="2026-01-01T00:00:00Z",
        dataset="d", dataset_hash=HEX, metric="accuracy", model_version="m",
        sample_size=10, seed=1,
    )
    assert r["hash_match"] is True
    assert r["threshold_satisfied"] is True
    assert r["ok"] is True


def test_verify_eval_log_missing_dataset_hash_errors(tmp_path: Path):
    """No dataset.sha in the log and no dataset_hash= override -> helpful error,
    not a crash and not a false TAMPERED."""
    h, _ = preregister(
        metric="accuracy", threshold=0.75, threshold_direction=">=",
        dataset="d", dataset_hash=HEX, model_version="m", sample_size=10, seed=1,
        pre_registered="2026-01-01T00:00:00Z", inspect_task="t",
    )
    p = _log_no_sha(tmp_path, value=0.80)
    with pytest.raises(MalformedLogError, match="dataset_hash"):
        verify_eval_log(
            p, expected_hash=h, threshold=0.75, threshold_direction=">=",
            pre_registered="2026-01-01T00:00:00Z",
            dataset="d", metric="accuracy", model_version="m", seed=1,
        )
