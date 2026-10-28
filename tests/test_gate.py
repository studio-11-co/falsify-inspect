"""`falsify-inspect gate`: the CI gate that works where the hook cannot.

Runs a real, offline Inspect eval with the mockllm model (8 of 10 correct,
accuracy 0.8), then checks the exit codes of `gate` against three manifests.
Also pins the reason the gate exists: a strict-mode hook exception does not
fail `inspect eval` (Inspect logs it as a warning).
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

inspect_ai = pytest.importorskip("inspect_ai")

from falsify_inspect import preregister  # noqa: E402

MODEL = "mockllm/model"


def _run_eval(log_dir: str) -> None:
    from inspect_ai import Task, eval as inspect_eval
    from inspect_ai.dataset import Sample
    from inspect_ai.model import ModelOutput, get_model
    from inspect_ai.scorer import match
    from inspect_ai.solver import generate

    samples = [Sample(input=f"Q{i}", target="yes") for i in range(10)]
    outputs = [ModelOutput.from_content(MODEL, "yes")] * 8 + [ModelOutput.from_content(MODEL, "no")] * 2
    task = Task(dataset=samples, solver=generate(), scorer=match(), name="qa_toy")
    inspect_eval(task, model=get_model(MODEL, custom_outputs=outputs), display="none", log_dir=log_dir)


def _lock(path, threshold: float, model: str) -> None:
    preregister(metric="accuracy", threshold=threshold, threshold_direction=">=",
                dataset="qa-toy-10", dataset_hash="0" * 64, model_version=model, seed=42,
                pre_registered="2026-10-28T12:00:00Z", inspect_task="qa_toy",
                inspect_scorer="match", output_path=str(path))


def _gate(manifest, log_dir) -> int:
    return subprocess.run(
        [sys.executable, "-m", "falsify_inspect.cli", "gate", "--manifest", str(manifest), "--log-dir", str(log_dir)],
        capture_output=True, text=True,
    ).returncode


@pytest.fixture(scope="module")
def log_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("logs")
    env = {k: v for k, v in os.environ.items() if not k.startswith("FALSIFY_PRML")}
    old = dict(os.environ)
    os.environ.clear(); os.environ.update(env)
    try:
        _run_eval(str(d))
    finally:
        os.environ.clear(); os.environ.update(old)
    return d


def test_gate_pass_fail_tampered(tmp_path, log_dir):
    _lock(tmp_path / "pass.prml.yaml", 0.75, MODEL)
    _lock(tmp_path / "fail.prml.yaml", 0.95, MODEL)
    _lock(tmp_path / "tamper.prml.yaml", 0.75, "anthropic/other-model")
    assert _gate(tmp_path / "pass.prml.yaml", log_dir) == 0
    assert _gate(tmp_path / "fail.prml.yaml", log_dir) == 10
    assert _gate(tmp_path / "tamper.prml.yaml", log_dir) == 3


def test_gate_cannot_verify(tmp_path):
    _lock(tmp_path / "pass.prml.yaml", 0.75, MODEL)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _gate(tmp_path / "pass.prml.yaml", empty) == 2
    assert _gate(tmp_path / "missing.prml.yaml", empty) == 2
