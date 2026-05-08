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
    extract_manifest_from_log,
    InspectManifest,
    PRMLVerificationError,
)

__version__ = "0.1.0"

__all__ = [
    "preregister",
    "verify_eval_log",
    "extract_manifest_from_log",
    "InspectManifest",
    "PRMLVerificationError",
    "__version__",
]
