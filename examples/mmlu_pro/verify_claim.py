"""Verify the checked-in MMLU-Pro example claim."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from falsify_inspect import verify_eval_log

HERE = Path(__file__).resolve().parent
EXPECTED_HASH = "sha256:218b553d49c6f1f4b1f100a1c143995cc4ece4cbda2e8366d0817060783f1026"


def verify() -> dict[str, Any]:
    manifest = yaml.safe_load((HERE / "claim.prml.yaml").read_text(encoding="utf-8"))
    return verify_eval_log(
        HERE / "sample_eval_log.json",
        expected_hash=EXPECTED_HASH,
        threshold=manifest["threshold"],
        threshold_direction=manifest["threshold_direction"],
        pre_registered=manifest["pre_registered"],
        sample_size=manifest["sample_size"],
        seed=manifest["seed"],
    )


def main() -> int:
    result = verify()
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
