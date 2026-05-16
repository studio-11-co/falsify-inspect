# MMLU-Pro PRML example

This example shows how to pre-register and verify a small Inspect AI
MMLU-Pro run with `falsify-inspect`.

## Files

- `mmlu_pro_prml.py` defines an Inspect AI task backed by the
  `TIGER-Lab/MMLU-Pro` Hugging Face dataset.
- `claim.prml.yaml` is the locked PRML manifest for a 10-sample run.
- `sample_eval_log.json` is a compact Inspect-shaped log that matches the
  manifest.
- `verify_claim.py` verifies the sample log against the pre-registered hash.

## Run the eval

From a source checkout, install the package with the optional Inspect
dependency first:

```bash
python -m pip install -e ".[inspect]"
```

Then run a small sample:

```bash
inspect eval examples/mmlu_pro/mmlu_pro_prml.py \
  --model openai/gpt-4o-mini \
  --limit 10 \
  --sample-shuffle 42
```

Before publishing a result, lock the claim fields that will be verified later:

```bash
falsify-inspect lock \
  --metric accuracy \
  --threshold 0.75 \
  --threshold-direction ">=" \
  --dataset TIGER-Lab/MMLU-Pro \
  --dataset-hash hf:527feea0afed1de15a8c115abf7be4c912123315 \
  --model-version openai/gpt-4o-mini \
  --sample-size 10 \
  --seed 42 \
  --task mmlu_pro_prml \
  --output examples/mmlu_pro/claim.prml.yaml
```

The checked-in manifest hashes to:

```text
sha256:218b553d49c6f1f4b1f100a1c143995cc4ece4cbda2e8366d0817060783f1026
```

## Verify the sample claim

```bash
python examples/mmlu_pro/verify_claim.py
```

The script exits with `0` when the hash matches and the observed accuracy
satisfies the pre-registered threshold.
