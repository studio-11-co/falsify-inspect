"""falsify-inspect — PRML v0.1 pre-registration for Inspect AI eval logs.

Manifests use the real PRML v0.1 schema and are hashed by the published
``falsify`` package (``falsify_prml``), so the hash matches the ``falsify`` CLI
and every other PRML reference implementation.

Usage:
    from falsify_inspect import preregister, verify_eval_log

    # Before running an eval:
    manifest_hash, manifest = preregister(
        metric="refusal_rate",
        threshold=0.95,
        threshold_direction=">=",                # -> PRML comparator
        dataset="harmbench-v1",                  # -> PRML dataset.id
        dataset_hash="3b1c...64hex",             # -> PRML dataset.hash (64 hex)
        model_version="claude-3.5-sonnet@2025-10-01",  # -> PRML producer.id
        seed=42,
        sample_size=500,                          # -> extra key
    )

    # After running:
    result = verify_eval_log(
        "eval.log",
        expected_hash=manifest_hash,
        threshold=0.95,
        threshold_direction=">=",
        pre_registered=manifest.created_at,
    )

CLI:
    falsify-inspect lock --metric refusal_rate --threshold 0.95 ...
    falsify-inspect verify eval.log --hash <64-hex>
"""

from falsify_inspect.core import (
    preregister,
    verify_eval_log,
    verify_live,
    verify_observation,
    load_committed_manifest,
    extract_manifest_from_log,
    InspectManifest,
    PRMLVerificationError,
    MalformedLogError,
)

# The Inspect hook (falsify_inspect.hooks.FalsifyHooks) is intentionally NOT
# imported here: it requires inspect_ai, and the manual API above must stay
# importable without it. Inspect loads the hook via the `inspect_ai` entry
# point (falsify_inspect._registry).

__version__ = "0.3.1"

__all__ = [
    "preregister",
    "verify_eval_log",
    "verify_live",
    "verify_observation",
    "load_committed_manifest",
    "extract_manifest_from_log",
    "InspectManifest",
    "PRMLVerificationError",
    "MalformedLogError",
    "__version__",
]
