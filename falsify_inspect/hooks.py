"""Inspect AI hook: verify an eval run against a pre-registered PRML manifest.

Enable by setting FALSIFY_PRML to the path of a pre-registered ``.prml.yaml``
(produced by ``falsify_inspect.preregister(...)`` or the ``falsify-inspect lock``
CLI), then run your eval as usual:

    export FALSIFY_PRML=harmbench.prml.yaml
    inspect eval harmbench.py

At the end of each task the hook reads the realised metric from the eval log,
checks it against the committed threshold, and confirms the run's identity
(model, dataset, task) matches what was pre-registered. It writes a
tamper-evident receipt and logs PASS / FAIL / TAMPERED.

Set FALSIFY_PRML_STRICT=1 to make a non-PASS verdict fail the run (a CI gate).
By default the hook is observe-only and never interrupts the eval.

This is the Inspect-native counterpart to the manual ``verify_eval_log`` API;
it mirrors the pattern of Inspect's own MLflow / W&B example hooks.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from inspect_ai.hooks import Hooks, TaskEnd, hooks

from falsify_inspect.core import verify_live

logger = logging.getLogger(__name__)

_MANIFEST_ENV = "FALSIFY_PRML"
_STRICT_ENV = "FALSIFY_PRML_STRICT"


class FalsifyVerificationFailed(Exception):
    """Raised in strict mode when a run does not PASS its PRML pre-registration."""


def _strict() -> bool:
    return os.getenv(_STRICT_ENV, "").lower() in {"1", "true", "yes", "on"}


def _observed_for_metric(log: Any, metric_name: str) -> float | None:
    """Find the realised value for ``metric_name`` in an EvalLog's scores.

    Matches on the scorer name, the metric name, or the ``scorer/metric``
    composite key, by exact match or by last path segment.
    """
    results = getattr(log, "results", None)
    scores = getattr(results, "scores", None) or []
    target = metric_name.split("/")[-1]
    for score in scores:
        scorer = getattr(score, "name", None) or getattr(score, "scorer", None) or ""
        metrics = getattr(score, "metrics", None) or {}
        for mname, metric in metrics.items():
            value = getattr(metric, "value", None)
            if value is None and isinstance(metric, dict):
                value = metric.get("value")
            if value is None:
                continue
            keys = {mname, mname.split("/")[-1], scorer, f"{scorer}/{mname}"}
            if metric_name in keys or target in keys:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
    return None


def _live_fields(log: Any, metric_name: str) -> dict[str, Any]:
    spec = getattr(log, "eval", None)
    dataset = getattr(spec, "dataset", None)
    return {
        "observed_value": _observed_for_metric(log, metric_name),
        "live_model": getattr(spec, "model", None),
        "live_dataset": getattr(dataset, "name", None),
        "live_dataset_hash": getattr(dataset, "sha", None),
        "live_task": getattr(spec, "task", None),
    }


def _write_receipt(verdict: dict[str, Any], task: str | None) -> None:
    safe_task = (task or "eval").replace("/", "_")
    path = Path.cwd() / f"{safe_task}.prml-receipt.json"
    try:
        path.write_text(json.dumps(verdict, indent=2, default=str), encoding="utf-8")
        logger.info("PRML receipt written to %s", path)
    except OSError:
        logger.debug("could not write PRML receipt to %s", path, exc_info=True)


@hooks(name="falsify_prml", description="PRML pre-registration verification")
class FalsifyHooks(Hooks):
    """Verify each Inspect task against a pre-registered PRML manifest.

    Active only when FALSIFY_PRML points at a committed ``.prml.yaml``.
    """

    def enabled(self) -> bool:
        return os.getenv(_MANIFEST_ENV) is not None

    async def on_task_end(self, data: TaskEnd) -> None:
        manifest_path = os.getenv(_MANIFEST_ENV)
        if not manifest_path:
            return

        log = getattr(data, "log", None)
        task = getattr(getattr(log, "eval", None), "task", None)

        try:
            # We need the committed metric name first, so peek the manifest.
            from falsify_inspect.core import load_committed_manifest

            committed, _ = load_committed_manifest(manifest_path)
            metric_name = committed.get("metric")
            if not metric_name:
                logger.warning("PRML manifest %s has no metric; skipping", manifest_path)
                return

            live = _live_fields(log, metric_name)
            verdict = verify_live(manifest_path=manifest_path, **live)
        except FileNotFoundError:
            logger.warning("PRML manifest not found at %s; skipping verification", manifest_path)
            return
        except Exception as exc:  # never break a non-strict eval on our account
            logger.warning("PRML verification error (skipping): %s", exc, exc_info=True)
            if _strict():
                raise FalsifyVerificationFailed(
                    f"PRML verification could not run: {exc}"
                ) from exc
            return

        status = verdict["status"]
        msg = (
            f"PRML {status} for task={task!r} metric={verdict.get('metric')!r} "
            f"observed={verdict.get('observed_value')} "
            f"{verdict.get('threshold_direction')} {verdict.get('threshold')} "
            f"(hash_match={verdict['hash_match']})"
        )
        if status == "PASS":
            logger.info(msg)
        else:
            logger.warning(msg)

        _write_receipt(verdict, task)

        if status != "PASS" and _strict():
            raise FalsifyVerificationFailed(msg)
