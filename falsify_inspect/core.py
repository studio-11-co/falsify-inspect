"""Core integration: PRML manifest generation + Inspect AI eval log verification."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


# -- Errors --------------------------------------------------------------------


class PRMLVerificationError(Exception):
    """Raised when an eval log fails PRML hash verification."""


class MalformedLogError(Exception):
    """Raised when the eval log is structurally invalid (missing required
    fields, unparseable shape) — distinct from PRMLVerificationError, which
    signals a hash/threshold disagreement on a *well-formed* log.

    The CLI maps this to exit 2 so CI consumers do not confuse a malformed
    log with a tamper signal (exit 3)."""


# -- Data class ----------------------------------------------------------------


@dataclass
class InspectManifest:
    """A PRML manifest scoped to Inspect AI eval logs.

    Wraps the eight required PRML v0.1 fields plus optional Inspect-specific
    metadata (task name, eval log path, scorer name).
    """

    metric: str
    value: float | None  # None at pre-registration; filled at verify time
    dataset: str
    dataset_hash: str
    model_version: str
    threshold: float
    threshold_direction: str  # ">=" | "<=" | "==" | ">" | "<"
    sample_size: int
    seed: int
    pre_registered: str  # RFC 3339
    prml_version: str = "0.1"

    # Inspect-specific (optional)
    inspect_task: str | None = None
    inspect_scorer: str | None = None

    def to_canonical_yaml(self) -> bytes:
        """Canonical byte serialisation per PRML v0.1 §4.

        - keys sorted alphabetically
        - strings double-quoted
        - floats rendered with Python's default repr (deterministic on CPython)
        - LF line endings, no trailing whitespace
        - UTF-8 encoded
        - `value` field excluded at lock time (filled at verify)
        """
        d = asdict(self)
        # exclude value at lock time — manifest commits the *threshold*,
        # the value is what we'll measure later
        d.pop("value", None)
        # exclude None-valued optional Inspect fields from the canonical hash
        d = {k: v for k, v in d.items() if v is not None}
        canonical = yaml.safe_dump(
            d,
            default_flow_style=False,
            sort_keys=True,
            width=float("inf"),
            allow_unicode=False,
        )
        # normalise line endings
        canonical = canonical.replace("\r\n", "\n").rstrip() + "\n"
        return canonical.encode("utf-8")

    def hash(self) -> str:
        h = hashlib.sha256(self.to_canonical_yaml()).hexdigest()
        return f"sha256:{h}"


# -- Public API ----------------------------------------------------------------


def preregister(
    *,
    metric: str,
    threshold: float,
    threshold_direction: str,
    dataset: str,
    dataset_hash: str,
    model_version: str,
    sample_size: int,
    seed: int,
    pre_registered: str | None = None,
    inspect_task: str | None = None,
    inspect_scorer: str | None = None,
    output_path: str | Path | None = None,
) -> tuple[str, InspectManifest]:
    """Create a PRML manifest before running an Inspect eval.

    Returns:
        (hash_string, manifest_object) — write the hash into your eval
        artifact, the manifest can be serialised to YAML and committed.
    """
    if pre_registered is None:
        pre_registered = (
            _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        )
        # ensure RFC 3339 trailing Z form
        if pre_registered.endswith("+00:00"):
            pre_registered = pre_registered[:-6] + "Z"

    if threshold_direction not in {">=", "<=", ">", "<", "=="}:
        raise ValueError(
            f"threshold_direction must be one of >= <= > < ==, got {threshold_direction!r}"
        )

    manifest = InspectManifest(
        metric=metric,
        value=None,
        dataset=dataset,
        dataset_hash=dataset_hash,
        model_version=model_version,
        threshold=threshold,
        threshold_direction=threshold_direction,
        sample_size=sample_size,
        seed=seed,
        pre_registered=pre_registered,
        inspect_task=inspect_task,
        inspect_scorer=inspect_scorer,
    )

    h = manifest.hash()

    if output_path is not None:
        Path(output_path).write_bytes(manifest.to_canonical_yaml())

    return h, manifest


def extract_manifest_from_log(log_path: str | Path) -> dict[str, Any]:
    """Extract Inspect AI eval log metadata into a PRML-compatible dict.

    Inspect logs are JSON. The fields we map:
        eval.task           -> inspect_task
        eval.model          -> model_version
        eval.dataset.name   -> dataset
        eval.dataset.sha    -> dataset_hash (when present)
        results.scores[0].metrics[primary].value -> value
        eval.config.epochs  -> sample_size (heuristic; user may override)
        eval.config.seed    -> seed

    Returns a dict with as many fields populated as the log supplies.
    Missing fields are returned as None — the caller fills them.
    """
    log_path = Path(log_path)
    if not log_path.exists():
        raise FileNotFoundError(log_path)

    raw = json.loads(log_path.read_text(encoding="utf-8"))

    # Inspect log structure (as of inspect_ai v0.3.x)
    eval_block = raw.get("eval", {})
    config = eval_block.get("config", {})
    dataset = eval_block.get("dataset", {})
    results = raw.get("results", {})
    scores = results.get("scores") or []

    primary_value: float | None = None
    primary_metric: str | None = None
    if scores:
        first = scores[0]
        primary_metric = first.get("name") or first.get("scorer")
        metrics = first.get("metrics") or {}
        # take the first metric in the dict
        for _name, m in metrics.items():
            v = m.get("value") if isinstance(m, dict) else None
            if v is not None:
                primary_value = float(v)
                break

    return {
        "inspect_task": eval_block.get("task"),
        "model_version": eval_block.get("model"),
        "dataset": dataset.get("name"),
        "dataset_hash": dataset.get("sha"),
        "metric": primary_metric,
        "value": primary_value,
        "sample_size": config.get("epochs") or config.get("sample_size"),
        "seed": config.get("seed"),
    }


def verify_eval_log(
    log_path: str | Path,
    *,
    expected_hash: str,
    threshold: float,
    threshold_direction: str,
    pre_registered: str,
    sample_size: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Reconstruct the pre-registered manifest from log metadata + caller's
    threshold/seed/etc., then verify the hash matches `expected_hash`.

    Returns a dict with keys:
        ok: bool — hash matches and threshold is satisfied
        hash_match: bool
        threshold_satisfied: bool
        observed_value: float | None
        manifest: dict (the reconstructed manifest)

    Raises:
        PRMLVerificationError if the log is structurally malformed.
    """
    extracted = extract_manifest_from_log(log_path)
    if not extracted.get("metric"):
        raise MalformedLogError(
            f"could not extract primary metric from log {log_path}: "
            "the log is structurally invalid (no `results.scores[].name`). "
            "This is not a tamper — it means the log shape is wrong."
        )

    fields = {
        "metric": extracted["metric"],
        "dataset": extracted["dataset"],
        "dataset_hash": extracted["dataset_hash"],
        "model_version": extracted["model_version"],
        "threshold": threshold,
        "threshold_direction": threshold_direction,
        "sample_size": sample_size or extracted["sample_size"],
        "seed": seed if seed is not None else extracted["seed"],
        "pre_registered": pre_registered,
        "inspect_task": extracted["inspect_task"],
    }
    missing = [k for k, v in fields.items() if v is None and k != "inspect_task"]
    if missing:
        raise MalformedLogError(
            f"missing fields after extraction: {missing}; supply via kwargs. "
            "This is a structurally invalid log, not a tamper."
        )

    manifest = InspectManifest(value=None, **fields)
    actual_hash = manifest.hash()
    hash_match = actual_hash == expected_hash

    observed = extracted.get("value")
    threshold_ok = False
    if observed is not None:
        ops = {
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            "==": lambda a, b: a == b,
        }
        threshold_ok = ops[threshold_direction](observed, threshold)

    return {
        "ok": hash_match and threshold_ok,
        "hash_match": hash_match,
        "threshold_satisfied": threshold_ok,
        "observed_value": observed,
        "expected_hash": expected_hash,
        "actual_hash": actual_hash,
        "manifest": asdict(manifest),
    }
