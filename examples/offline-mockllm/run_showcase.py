"""Fully offline, deterministic Inspect AI x PRML showcase -- no API key, no network.

Runs a *real* Inspect AI evaluation with the `mockllm` model (so it reproduces
byte-for-byte anywhere), pre-registers the claim's identity with PRML *before*
the run, then verifies the live run against the committed manifest with the
adapter's native `verify_live` path.

  A. Honest run  -- pre-register {accuracy >= 0.75, model mockllm}, run, observe
                    0.80, verify -> PASS.
  B. Swapped model -- pre-register the SAME claim for a *different* model, run on
                    mockllm, verify -> TAMPERED (the run's identity does not
                    match what was sealed; the hash breaks).

Run:  python run_showcase.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from inspect_ai import Task, eval as inspect_eval
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.scorer import match
from inspect_ai.solver import generate

from falsify_inspect import preregister, verify_live

HERE = Path(__file__).resolve().parent
PRE_REGISTERED = "2026-06-29T12:00:00Z"
MODEL = "mockllm/model"
DATASET_ID = "qa-toy-10"

SAMPLES = [Sample(input=f"Q{i}: is the sky blue?", target="yes") for i in range(10)]
OUTPUTS = [ModelOutput.from_content(MODEL, "yes")] * 8 + [ModelOutput.from_content(MODEL, "no")] * 2
DATASET_HASH = hashlib.sha256(
    json.dumps([{"input": s.input, "target": s.target} for s in SAMPLES], sort_keys=True).encode()
).hexdigest()


def run_eval_observed() -> float:
    """Run the real Inspect eval with mockllm; return observed accuracy."""
    task = Task(dataset=SAMPLES, solver=generate(), scorer=match())
    logs = inspect_eval(task, model=get_model(MODEL, custom_outputs=OUTPUTS),
                        display="none", log_dir=str(HERE / "logs"))
    metrics = logs[0].results.scores[0].metrics
    return float(metrics["accuracy"].value)


def lock(model_version: str, threshold: float, path: Path) -> str:
    h, _ = preregister(
        metric="accuracy", threshold=threshold, threshold_direction=">=",
        dataset=DATASET_ID, dataset_hash=DATASET_HASH, model_version=model_version,
        seed=42, pre_registered=PRE_REGISTERED, inspect_task="qa_toy",
        inspect_scorer="match", output_path=str(path),
    )
    return h


def banner(t: str) -> None:
    print(f"\n{'=' * 66}\n{t}\n{'=' * 66}")


def main() -> int:
    observed = run_eval_observed()

    # ---- A: honest run, pre-registered for the model actually used ----------
    banner("A. Honest run -- pre-registered {accuracy >= 0.75, model mockllm}")
    claim_a = HERE / "claim_A.prml.yaml"
    h_a = lock(MODEL, 0.75, claim_a)
    print(f"locked BEFORE run   sha256={h_a}")
    print(f"  bar: accuracy >= 0.75   model={MODEL}   dataset={DATASET_HASH[:16]}...")
    print(f"ran Inspect (mockllm)  observed accuracy = {observed:.4f}")
    res_a = verify_live(manifest_path=str(claim_a), observed_value=observed,
                        live_model=MODEL, live_task="qa_toy")
    print(f"verify_live -> {res_a['status']}")

    # ---- B: same claim sealed for a DIFFERENT model than the run ------------
    banner("B. Swapped model -- sealed for claude-3.5, but the run was mockllm")
    claim_b = HERE / "claim_B.prml.yaml"
    h_b = lock("anthropic/claude-3.5-sonnet", 0.75, claim_b)
    print(f"locked BEFORE run   sha256={h_b}   (model: anthropic/claude-3.5-sonnet)")
    print(f"ran Inspect (mockllm)  observed accuracy = {observed:.4f}")
    print("...the published run was actually on mockllm, not the sealed model...")
    res_b = verify_live(manifest_path=str(claim_b), observed_value=observed,
                        live_model=MODEL, live_task="qa_toy")
    print(f"verify_live -> {res_b['status']}   (identity does not match the sealed claim)")

    # ---- Result -------------------------------------------------------------
    ok = res_a["status"] == "PASS" and res_b["status"] == "TAMPERED"
    banner("RESULT")
    print(f"A honest run    : {res_a['status']}   (expected PASS)")
    print(f"B swapped model : {res_b['status']}   (expected TAMPERED)")
    print("\nPRML tied a real Inspect eval to its pre-registered identity -- "
          "a swapped model breaks the seal, checkable offline by anyone."
          if ok else "\nUNEXPECTED -- see above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
