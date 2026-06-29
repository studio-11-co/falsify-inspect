"""Core integration: PRML v0.1 manifest generation + Inspect AI eval log verification.

This adapter is a thin Inspect-AI-shaped layer over the published ``falsify``
package's reference implementation (``falsify_prml``). It does NOT carry its own
canonicalization, hashing, validation or predicate logic — all of that is
delegated to ``falsify_prml`` so the hash an Inspect user commits is byte-for-byte
the same one the ``falsify`` CLI, the JS/Go/Rust reference impls, and every other
PRML surface produce. See https://spec.falsify.dev/v0.1.

Manifests follow the real PRML v0.1 schema (nine required fields)::

    version: prml/0.1
    claim_id: <stable id>
    created_at: <RFC 3339>
    metric: <name>
    comparator: ">=" | "<=" | ">" | "<" | "=="
    threshold: <float>
    dataset: {id: <name>, hash: <64 lowercase hex>}
    seed: <int>
    producer: {id: <model/org id>}

Inspect-specific context (task name, scorer name, sample size) is carried as
extra top-level keys (``inspect_task``, ``inspect_scorer``, ``sample_size``).
``falsify_prml.validate_manifest`` allows unknown keys, and they participate in
the canonical hash like any other field.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import falsify_prml as _prml
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


# Comparators accepted by PRML v0.1 (mirrors falsify_prml.VALID_COMPARATORS).
_COMPARATORS = {">=", "<=", ">", "<", "=="}

# Inspect-specific extra keys carried in the manifest alongside the nine
# required PRML fields. These are NOT part of the PRML schema, but PRML allows
# extra keys; they are hashed like everything else.
_EXTRA_KEYS = ("inspect_task", "inspect_scorer", "sample_size")


# -- Data class ----------------------------------------------------------------


@dataclass
class InspectManifest:
    """A PRML v0.1 manifest scoped to Inspect AI eval logs.

    Holds the real PRML v0.1 fields. Identity that an Inspect run exposes maps
    onto the PRML v0.1 schema as follows:

        metric            -> metric
        threshold         -> threshold
        comparator        -> comparator
        dataset_id        -> dataset.id
        dataset_hash      -> dataset.hash   (64 lowercase hex)
        producer_id       -> producer.id
        seed              -> seed
        created_at (RFC 3339) -> created_at
        inspect_task      -> extra key ``inspect_task``
        inspect_scorer    -> extra key ``inspect_scorer``
        sample_size       -> extra key ``sample_size``
    """

    metric: str
    comparator: str  # ">=" | "<=" | "==" | ">" | "<"
    threshold: float
    dataset_id: str
    dataset_hash: str
    producer_id: str
    seed: int
    created_at: str  # RFC 3339
    claim_id: str
    version: str = "prml/0.1"

    # Inspect-specific (optional) — carried as extra top-level keys
    inspect_task: str | None = None
    inspect_scorer: str | None = None
    sample_size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Render the real PRML v0.1 manifest dict (the thing that gets hashed).

        None-valued optional Inspect fields are omitted so they do not change
        the canonical bytes when unset.
        """
        m: dict[str, Any] = {
            "version": self.version,
            "claim_id": self.claim_id,
            "created_at": self.created_at,
            "metric": self.metric,
            "comparator": self.comparator,
            "threshold": self.threshold,
            "dataset": {"id": self.dataset_id, "hash": self.dataset_hash},
            "seed": self.seed,
            "producer": {"id": self.producer_id},
        }
        for key in _EXTRA_KEYS:
            value = getattr(self, key)
            if value is not None:
                m[key] = value
        return m

    def hash(self) -> str:
        """Return the canonical PRML SHA-256 (64 lowercase hex) of this manifest.

        Delegates to ``falsify_prml.manifest_hash`` — identical bytes to the
        ``falsify`` CLI and all reference implementations.
        """
        return _prml.manifest_hash(self.to_dict())

    def to_canonical_yaml(self) -> bytes:
        """Canonical byte serialisation per PRML v0.1 §4 (via falsify_prml)."""
        return _prml.canonicalize(self.to_dict()).encode("utf-8")


def _manifest_from_fields(fields: dict[str, Any]) -> InspectManifest:
    """Build an :class:`InspectManifest` from a real PRML v0.1 manifest dict.

    Accepts the nested ``dataset``/``producer`` shape plus the Inspect extra
    keys. Used when loading a committed manifest off disk.
    """
    ds = fields.get("dataset") or {}
    prod = fields.get("producer") or {}
    if not isinstance(ds, dict) or not isinstance(prod, dict):
        raise MalformedLogError(
            "manifest dataset/producer must be mappings (real PRML v0.1 schema)"
        )
    return InspectManifest(
        metric=fields.get("metric"),
        comparator=fields.get("comparator"),
        threshold=fields.get("threshold"),
        dataset_id=ds.get("id"),
        dataset_hash=ds.get("hash"),
        producer_id=prod.get("id"),
        seed=fields.get("seed"),
        created_at=fields.get("created_at"),
        claim_id=fields.get("claim_id"),
        version=fields.get("version", "prml/0.1"),
        inspect_task=fields.get("inspect_task"),
        inspect_scorer=fields.get("inspect_scorer"),
        sample_size=fields.get("sample_size"),
    )


# -- Public API ----------------------------------------------------------------


def preregister(
    *,
    metric: str,
    threshold: float,
    threshold_direction: str,
    dataset: str,
    dataset_hash: str,
    model_version: str,
    seed: int,
    claim_id: str | None = None,
    sample_size: int | None = None,
    pre_registered: str | None = None,
    inspect_task: str | None = None,
    inspect_scorer: str | None = None,
    output_path: str | Path | None = None,
) -> tuple[str, InspectManifest]:
    """Create a PRML v0.1 manifest before running an Inspect eval.

    ``threshold_direction`` is the adapter-facing name for the PRML
    ``comparator`` field (kept for backwards-compatible call sites).

    ``dataset_hash`` must be 64 lowercase hex chars (a SHA-256 of the dataset),
    per PRML v0.1. ``claim_id`` defaults to a value derived from the dataset and
    metric if not supplied.

    Returns:
        (hash_string, manifest_object) — the hash is the bare 64-hex canonical
        PRML SHA-256 (no ``sha256:`` prefix). Write it into your eval artifact;
        the manifest can be serialised to canonical YAML and committed.

    Raises:
        ValueError if the resulting manifest is invalid per
        ``falsify_prml.validate_manifest`` (bad comparator, non-hex dataset
        hash, control chars, etc.).
    """
    if threshold_direction not in _COMPARATORS:
        raise ValueError(
            f"threshold_direction must be one of >= <= > < ==, got {threshold_direction!r}"
        )

    if pre_registered is None:
        pre_registered = (
            _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        )
        if pre_registered.endswith("+00:00"):
            pre_registered = pre_registered[:-6] + "Z"

    if claim_id is None:
        claim_id = f"{dataset}:{metric}"

    manifest = InspectManifest(
        metric=metric,
        comparator=threshold_direction,
        threshold=threshold,
        dataset_id=dataset,
        dataset_hash=dataset_hash,
        producer_id=model_version,
        seed=seed,
        created_at=pre_registered,
        claim_id=claim_id,
        inspect_task=inspect_task,
        inspect_scorer=inspect_scorer,
        sample_size=sample_size,
    )

    errors = _prml.validate_manifest(manifest.to_dict())
    if errors:
        raise ValueError("invalid PRML manifest: " + "; ".join(errors))

    h = manifest.hash()

    if output_path is not None:
        Path(output_path).write_bytes(manifest.to_canonical_yaml())

    return h, manifest


def extract_manifest_from_log(log_path: str | Path) -> dict[str, Any]:
    """Extract Inspect AI eval log metadata into a PRML-compatible dict.

    Inspect logs are JSON. The fields we map to PRML v0.1 names:
        eval.task           -> inspect_task
        eval.model          -> producer_id   (PRML producer.id)
        eval.dataset.name   -> dataset_id    (PRML dataset.id)
        eval.dataset.sha    -> dataset_hash  (PRML dataset.hash, when present)
        results.scores[0].metrics[primary].value -> value (observed)
        eval.config.epochs  -> sample_size (heuristic; user may override)
        eval.config.seed    -> seed

    Returns a dict with as many fields populated as the log supplies.
    Missing fields are returned as None — the caller fills them.
    """
    import json

    log_path = Path(log_path)
    if not log_path.exists():
        raise FileNotFoundError(log_path)

    raw = json.loads(log_path.read_text(encoding="utf-8"))

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
        for _name, m in metrics.items():
            v = m.get("value") if isinstance(m, dict) else None
            if v is not None:
                primary_value = float(v)
                break

    return {
        "inspect_task": eval_block.get("task"),
        "producer_id": eval_block.get("model"),
        "dataset_id": dataset.get("name"),
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
    claim_id: str | None = None,
    dataset: str | None = None,
    model_version: str | None = None,
    sample_size: int | None = None,
    seed: int | None = None,
    inspect_scorer: str | None = None,
    dataset_hash: str | None = None,
    metric: str | None = None,
) -> dict[str, Any]:
    """Reconstruct the pre-registered manifest from log metadata + caller's
    threshold/seed/etc., then verify the hash matches ``expected_hash``.

    The reconstructed manifest must reproduce the exact PRML v0.1 manifest that
    was locked, so the caller supplies the fields the eval log does not carry
    (threshold, comparator, created_at/pre_registered, and — because the log has
    no claim_id — the same ``claim_id`` used at lock, defaulting to
    ``"{dataset}:{metric}"`` as in :func:`preregister`).

    Current Inspect logs do not record ``eval.dataset.sha`` (and the scorer name,
    not the metric, is what lands in ``results.scores[].name``). Pass
    ``dataset_hash=`` and ``metric=`` to supply what the log omits; both default
    to whatever the log does carry, so logs that include those fields keep
    working unchanged.

    Returns a dict with keys:
        ok, hash_match, threshold_satisfied, observed_value,
        expected_hash, actual_hash, manifest

    Raises:
        MalformedLogError if the log is structurally malformed.
    """
    extracted = extract_manifest_from_log(log_path)
    metric = metric if metric is not None else extracted.get("metric")
    if not metric:
        raise MalformedLogError(
            f"could not determine the metric for log {log_path}: the log has no "
            "`results.scores[].name` and no `metric=` override was supplied."
        )
    dataset_id = dataset if dataset is not None else extracted["dataset_id"]
    producer_id = (
        model_version if model_version is not None else extracted["producer_id"]
    )
    fields = {
        "metric": metric,
        "comparator": threshold_direction,
        "threshold": threshold,
        "dataset_id": dataset_id,
        "dataset_hash": dataset_hash if dataset_hash is not None else extracted["dataset_hash"],
        "producer_id": producer_id,
        "sample_size": sample_size if sample_size is not None else extracted["sample_size"],
        "seed": seed if seed is not None else extracted["seed"],
        "created_at": pre_registered,
        "claim_id": claim_id if claim_id is not None else f"{dataset_id}:{metric}",
        "inspect_task": extracted["inspect_task"],
        "inspect_scorer": inspect_scorer,
    }
    required = ("metric", "dataset_id", "dataset_hash", "producer_id", "seed")
    missing = [k for k in required if fields[k] is None]
    if missing:
        raise MalformedLogError(
            "the log does not carry these fields and no override was supplied: "
            f"{missing}. Current Inspect logs omit dataset.sha, so pass "
            "dataset_hash= (and dataset=/seed=/model_version=/metric= as needed). "
            "This is a missing field, not a tamper."
        )

    manifest = InspectManifest(
        metric=fields["metric"],
        comparator=fields["comparator"],
        threshold=fields["threshold"],
        dataset_id=fields["dataset_id"],
        dataset_hash=fields["dataset_hash"],
        producer_id=fields["producer_id"],
        seed=fields["seed"],
        created_at=fields["created_at"],
        claim_id=fields["claim_id"],
        inspect_task=fields["inspect_task"],
        inspect_scorer=fields["inspect_scorer"],
        sample_size=fields["sample_size"],
    )
    actual_hash = manifest.hash()
    hash_match = actual_hash == expected_hash

    observed = extracted.get("value")
    threshold_ok = False
    if observed is not None:
        threshold_ok = _prml.evaluate_predicate(observed, threshold_direction, threshold)

    return {
        "ok": hash_match and threshold_ok,
        "hash_match": hash_match,
        "threshold_satisfied": threshold_ok,
        "observed_value": observed,
        "expected_hash": expected_hash,
        "actual_hash": actual_hash,
        "manifest": manifest.to_dict(),
    }


# -- Hook support (in-memory verification) -------------------------------------
#
# These helpers exist so the Inspect hook (falsify_inspect.hooks) can verify a
# live EvalLog object without writing it to disk first.


def load_committed_manifest(path: str | Path) -> tuple[dict[str, Any], str]:
    """Load a pre-registered ``.prml.yaml`` and return ``(fields, hash)``.

    The committed hash is the *canonical* PRML hash of the parsed manifest
    (``falsify_prml.manifest_hash``), NOT a hash of the raw file bytes. This is
    the value :func:`preregister` returned at lock time and the value every PRML
    surface re-derives, so it is robust to incidental file reformatting.
    """
    fields = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(fields, dict):
        raise MalformedLogError(
            f"manifest at {path} did not parse to a mapping (got {type(fields).__name__})"
        )
    committed_hash = _prml.manifest_hash(fields)
    return fields, committed_hash


def verify_observation(
    *,
    expected_hash: str,
    observed_value: float | None,
    metric: str,
    dataset_id: str | None,
    dataset_hash: str | None,
    producer_id: str | None,
    threshold: float,
    comparator: str,
    seed: int | None,
    created_at: str,
    claim_id: str | None = None,
    sample_size: int | None = None,
    inspect_task: str | None = None,
    inspect_scorer: str | None = None,
) -> dict[str, Any]:
    """Rebuild a manifest from PRML v0.1 identity fields + observed value, then
    return a verdict dict with an explicit ``status`` of PASS / FAIL / TAMPERED.

    Kwargs use the PRML v0.1 vocabulary (``comparator``, ``producer_id``,
    ``dataset_id``, ``dataset_hash`` -> ``dataset.hash``, ``created_at``).

    TAMPERED means the rebuilt hash does not equal ``expected_hash`` (the run's
    identity, e.g. model or dataset, does not match what was pre-registered).
    FAIL means the hash matches but the observed value misses the threshold.
    """
    if comparator not in _COMPARATORS:
        raise ValueError(
            f"comparator must be one of >= <= > < ==, got {comparator!r}"
        )
    if claim_id is None:
        claim_id = f"{dataset_id}:{metric}"
    manifest = InspectManifest(
        metric=metric,
        comparator=comparator,
        threshold=threshold,
        dataset_id=dataset_id,
        dataset_hash=dataset_hash,
        producer_id=producer_id,
        seed=seed,
        created_at=created_at,
        claim_id=claim_id,
        inspect_task=inspect_task,
        inspect_scorer=inspect_scorer,
        sample_size=sample_size,
    )
    actual_hash = manifest.hash()
    hash_match = actual_hash == expected_hash
    threshold_ok = (
        observed_value is not None
        and _prml.evaluate_predicate(observed_value, comparator, threshold)
    )
    if not hash_match:
        status = "TAMPERED"
    elif threshold_ok:
        status = "PASS"
    else:
        status = "FAIL"
    return {
        "ok": hash_match and threshold_ok,
        "status": status,
        "hash_match": hash_match,
        "threshold_satisfied": threshold_ok,
        "observed_value": observed_value,
        "expected_hash": expected_hash,
        "actual_hash": actual_hash,
        "manifest": manifest.to_dict(),
    }


def verify_live(
    *,
    manifest_path: str | Path,
    observed_value: float | None,
    live_model: str | None = None,
    live_dataset: str | None = None,
    live_dataset_hash: str | None = None,
    live_task: str | None = None,
) -> dict[str, Any]:
    """Verify a live run against a committed manifest file.

    Loads the pre-registered manifest (its committed hash is the canonical PRML
    hash of its contents), overrides the identity fields the eval run actually
    used (model -> producer.id, dataset -> dataset.id/hash, task ->
    inspect_task) where the caller supplies them, rebuilds the manifest, and
    compares. A mismatch means the run did not match the pre-registration
    (TAMPERED); a match with a missed threshold is FAIL; a match that meets it
    is PASS.

    All committed fields not supplied by the live run are taken from the
    manifest as committed, so they do not falsely trigger TAMPERED when the eval
    log does not expose them.
    """
    committed, committed_hash = load_committed_manifest(manifest_path)
    manifest = _manifest_from_fields(committed)

    if live_model is not None:
        manifest.producer_id = live_model
    if live_dataset is not None:
        manifest.dataset_id = live_dataset
    if live_dataset_hash is not None:
        manifest.dataset_hash = live_dataset_hash
    if manifest.inspect_task is not None and live_task is not None:
        manifest.inspect_task = live_task

    actual_hash = manifest.hash()
    hash_match = actual_hash == committed_hash

    comparator = manifest.comparator
    threshold = manifest.threshold
    threshold_ok = (
        observed_value is not None
        and comparator in _COMPARATORS
        and threshold is not None
        and _prml.evaluate_predicate(observed_value, comparator, threshold)
    )
    if not hash_match:
        status = "TAMPERED"
    elif threshold_ok:
        status = "PASS"
    else:
        status = "FAIL"
    return {
        "ok": hash_match and threshold_ok,
        "status": status,
        "hash_match": hash_match,
        "threshold_satisfied": threshold_ok,
        "observed_value": observed_value,
        "threshold": threshold,
        "comparator": comparator,
        "metric": manifest.metric,
        "expected_hash": committed_hash,
        "actual_hash": actual_hash,
    }
