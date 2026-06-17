"""Tests for the PRML pre-registration verification: verify_live (pure) and
the Inspect hook (FalsifyHooks, skipped when inspect_ai is absent)."""

from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace

import pytest

from falsify_inspect import load_committed_manifest, preregister, verify_live


HEX = "c" * 64


def _make_manifest(tmp_path, **over):
    kw = dict(
        metric="accuracy",
        threshold=0.85,
        threshold_direction=">=",
        dataset="imagenet-val",
        dataset_hash=HEX,
        model_version="m@1",
        sample_size=100,
        seed=42,
        inspect_task="mytask",
    )
    kw.update(over)
    path = tmp_path / "x.prml.yaml"
    h, _ = preregister(output_path=str(path), **kw)
    return path, h


# -- verify_live (no inspect_ai needed) ---------------------------------------


def test_verify_live_pass(tmp_path):
    path, h = _make_manifest(tmp_path)
    v = verify_live(
        manifest_path=str(path),
        observed_value=0.90,
        live_model="m@1",
        live_dataset="imagenet-val",
        live_task="mytask",
    )
    assert v["status"] == "PASS"
    assert v["ok"] and v["hash_match"] and v["threshold_satisfied"]
    assert v["expected_hash"] == h


def test_verify_live_fail_threshold(tmp_path):
    path, _ = _make_manifest(tmp_path)
    v = verify_live(
        manifest_path=str(path),
        observed_value=0.50,
        live_model="m@1",
        live_dataset="imagenet-val",
        live_task="mytask",
    )
    assert v["status"] == "FAIL"
    assert v["hash_match"] and not v["threshold_satisfied"] and not v["ok"]


def test_verify_live_tampered_model(tmp_path):
    path, _ = _make_manifest(tmp_path)
    v = verify_live(
        manifest_path=str(path),
        observed_value=0.99,
        live_model="DIFFERENT@2",
        live_dataset="imagenet-val",
        live_task="mytask",
    )
    assert v["status"] == "TAMPERED"
    assert not v["hash_match"] and not v["ok"]


def test_verify_live_tampered_dataset(tmp_path):
    path, _ = _make_manifest(tmp_path)
    v = verify_live(
        manifest_path=str(path),
        observed_value=0.99,
        live_model="m@1",
        live_dataset="OTHER-DATASET",
        live_task="mytask",
    )
    assert v["status"] == "TAMPERED"


def test_verify_live_tampered_task(tmp_path):
    path, _ = _make_manifest(tmp_path)
    v = verify_live(
        manifest_path=str(path),
        observed_value=0.99,
        live_model="m@1",
        live_dataset="imagenet-val",
        live_task="some-other-task",
    )
    assert v["status"] == "TAMPERED"


def test_verify_live_none_falls_back_to_committed(tmp_path):
    # When the live run does not expose identity fields, committed values are
    # used, so a clean run still matches.
    path, h = _make_manifest(tmp_path)
    v = verify_live(manifest_path=str(path), observed_value=0.9)
    assert v["status"] == "PASS"
    assert v["expected_hash"] == h


def test_load_committed_manifest_roundtrip(tmp_path):
    path, h = _make_manifest(tmp_path)
    fields, committed_hash = load_committed_manifest(str(path))
    assert committed_hash == h
    assert fields["metric"] == "accuracy"
    assert fields["threshold"] == 0.85
    # Real PRML v0.1 nesting: model -> producer.id, comparator, dataset.hash.
    assert fields["producer"]["id"] == "m@1"
    assert fields["comparator"] == ">="
    assert fields["dataset"]["id"] == "imagenet-val"
    assert fields["dataset"]["hash"] == HEX


# -- the Inspect hook (requires inspect_ai) -----------------------------------


def _mock_log(model="m@1", dataset="imagenet-val", task="mytask", value=0.90):
    return SimpleNamespace(
        eval=SimpleNamespace(
            model=model,
            task=task,
            dataset=SimpleNamespace(name=dataset, sha=None),
        ),
        results=SimpleNamespace(
            scores=[
                SimpleNamespace(
                    name="accuracy",
                    metrics={"accuracy": SimpleNamespace(value=value)},
                )
            ]
        ),
        status="success",
    )


def test_observed_for_metric():
    pytest.importorskip("inspect_ai")
    from falsify_inspect.hooks import _observed_for_metric

    assert _observed_for_metric(_mock_log(value=0.91), "accuracy") == 0.91
    assert _observed_for_metric(_mock_log(value=0.91), "missing") is None


def test_hook_pass_writes_receipt(tmp_path, monkeypatch):
    pytest.importorskip("inspect_ai")
    from falsify_inspect.hooks import FalsifyHooks

    path, _ = _make_manifest(tmp_path)
    monkeypatch.setenv("FALSIFY_PRML", str(path))
    monkeypatch.chdir(tmp_path)

    hook = FalsifyHooks()
    assert hook.enabled() is True
    data = SimpleNamespace(log=_mock_log(value=0.90))
    asyncio.run(hook.on_task_end(data))

    receipt = tmp_path / "mytask.prml-receipt.json"
    assert receipt.exists()
    verdict = json.loads(receipt.read_text())
    assert verdict["status"] == "PASS"


def test_hook_strict_raises_on_tamper(tmp_path, monkeypatch):
    pytest.importorskip("inspect_ai")
    from falsify_inspect.hooks import FalsifyHooks, FalsifyVerificationFailed

    path, _ = _make_manifest(tmp_path)
    monkeypatch.setenv("FALSIFY_PRML", str(path))
    monkeypatch.setenv("FALSIFY_PRML_STRICT", "1")
    monkeypatch.chdir(tmp_path)

    hook = FalsifyHooks()
    data = SimpleNamespace(log=_mock_log(model="SWAPPED@9", value=0.99))
    with pytest.raises(FalsifyVerificationFailed):
        asyncio.run(hook.on_task_end(data))


def test_hook_disabled_without_env(monkeypatch):
    pytest.importorskip("inspect_ai")
    from falsify_inspect.hooks import FalsifyHooks

    monkeypatch.delenv("FALSIFY_PRML", raising=False)
    assert FalsifyHooks().enabled() is False
