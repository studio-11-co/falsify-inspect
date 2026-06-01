"""falsify-inspect — PRML pre-registration for Inspect AI eval logs.

Usage:
    from falsify_inspect import preregister, verify_eval_log

    # Before running an eval:
    manifest_hash = preregister(
        metric="refusal_rate",
        threshold=0.95,
        threshold_direction=">=",
        dataset="harmbench-v1",
        dataset_hash="sha256:abc123...",
        model_version="claude-3.5-sonnet@2025-10-01",
        sample_size=500,
        seed=42,
    )

    # After running:
    is_valid = verify_eval_log("eval.log", expected_hash=manifest_hash)

CLI:
    falsify-inspect lock --metric refusal_rate --threshold 0.95 ...
    falsify-inspect verify eval.log --hash sha256:...
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

__version__ = "0.2.0"

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
