"""Verify the checked-in MMLU-Pro example claim against the sample eval log.

Uses ``verify_live``: it loads the committed PRML v0.1 manifest
(``claim.prml.yaml``), recomputes its canonical hash, overrides the identity
fields the eval run actually exposes (model -> producer.id, dataset ->
dataset.id/hash, task -> inspect_task), then re-derives the hash and checks the
observed metric against the committed threshold.

A clean run yields status PASS (hash matches AND threshold satisfied).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from falsify_inspect import verify_live

HERE = Path(__file__).resolve().parent
# Canonical PRML v0.1 hash of claim.prml.yaml (re-derivable with
# `falsify hash claim.prml.yaml` or falsify_prml.manifest_hash(<parsed yaml>)).
EXPECTED_HASH = "475c25dc2f7e4a268bd502ecb4e668bf04638a285e7d1d3350581d6ce55d7759"


def verify() -> dict[str, Any]:
    log = json.loads((HERE / "sample_eval_log.json").read_text(encoding="utf-8"))
    eval_block = log["eval"]
    dataset = eval_block["dataset"]
    observed = log["results"]["scores"][0]["metrics"]["accuracy"]["value"]
    return verify_live(
        manifest_path=HERE / "claim.prml.yaml",
        observed_value=observed,
        live_model=eval_block["model"],
        live_dataset=dataset["name"],
        live_dataset_hash=dataset["sha"],
        live_task=eval_block["task"],
    )


def main() -> int:
    result = verify()
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
