# falsify-inspect

PRML pre-registration for [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) eval logs.

[![PyPI](https://img.shields.io/pypi/v/falsify-inspect.svg)](https://pypi.org/project/falsify-inspect/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRML v0.1](https://img.shields.io/badge/PRML-v0.1-39D98A.svg)](https://spec.falsify.dev/v0.1)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/studio-11-co/falsify-inspect/badge)](https://scorecard.dev/viewer/?uri=github.com/studio-11-co/falsify-inspect)
[![CI](https://github.com/studio-11-co/falsify-inspect/actions/workflows/test.yml/badge.svg)](https://github.com/studio-11-co/falsify-inspect/actions/workflows/test.yml)

> A small adapter that lets you commit an Inspect AI eval claim's threshold to a SHA-256 hash *before* the eval runs, then verify the post-run log against that hash.

---

## Why

Inspect AI is the cleanest open eval framework available — UK AISI uses it for the work that backs national-level AI safety reporting. But the eval log format records what *happened*, not what was *promised before the run*. PRML closes that gap.

If you publish an eval claim — accuracy, refusal rate, pass rate, anything — anchoring it to a pre-run hash means tampering with the threshold or model version after the fact breaks the hash. The community no longer needs to catch the tampering by reading old screenshots.

## Install

```bash
pip install falsify-inspect
```

## Quickstart — Python API

```python
from falsify_inspect import preregister, verify_eval_log

# 1. Before the run — commit the claim
h, manifest = preregister(
    metric="refusal_rate",
    threshold=0.95,
    threshold_direction=">=",
    dataset="harmbench-v1",
    dataset_hash="sha256:abc...",
    model_version="claude-3.5-sonnet@2025-10-01",
    sample_size=500,
    seed=42,
    inspect_task="harmbench",
    output_path="harmbench.prml.yaml",
)
print(h)
# sha256:e3b0c44298fc1c14...

# 2. Run your inspect eval as usual, producing eval.log
# (no changes to your inspect code)

# 3. After the run — verify
result = verify_eval_log(
    "eval.log",
    expected_hash=h,
    threshold=0.95,
    threshold_direction=">=",
    pre_registered=manifest.pre_registered,
)
assert result["ok"]
```

## Quickstart — CLI

```bash
# Pre-register an eval claim
falsify-inspect lock \
  --metric refusal_rate \
  --threshold 0.95 \
  --threshold-direction ">=" \
  --dataset harmbench-v1 \
  --dataset-hash sha256:abc... \
  --model-version "claude-3.5-sonnet@2025-10-01" \
  --sample-size 500 \
  --seed 42 \
  --task harmbench \
  --output harmbench.prml.yaml

# returns: sha256:e3b0c44298fc1c14...

# Later, verify the eval log
falsify-inspect verify eval.log \
  --hash sha256:e3b0c44298fc1c14... \
  --threshold 0.95 \
  --threshold-direction ">=" \
  --pre-registered "2026-05-08T20:00:00Z"
```

Exit codes:
- `0` — pass (hash matches, threshold satisfied)
- `10` — fail (hash matches, threshold violated)
- `3` — tamper (hash mismatch — fields changed after pre-registration)
- `2` — log not found / structurally invalid

## What this plugin does *not* do

- Does not modify `inspect_ai` itself. It reads existing eval log JSON.
- Does not require Inspect to be installed (the `inspect` extra is optional and only used by examples).
- Does not commit you to publishing every claim you pre-register. PRML §8.1 names this limit explicitly. Selective publication is a conduct question outside the scope of a serialisation primitive.

## Spec & licensing

- PRML v0.1 spec: [spec.falsify.dev/v0.1](https://spec.falsify.dev/v0.1) (CC BY 4.0)
- This package: MIT
- Patent non-assertion grant: [appendix of the spec](https://spec.falsify.dev/v0.1#appendix-patent-grant)

## Authors

Cüneyt Öztürk, co-founder, Studio 11 Turkey Ltd. Şti.
Contact: hello@studio-11.co · [falsify.dev](https://falsify.dev)
