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

Before publishing a result, lock the claim fields that will be verified later.
Manifests follow the real **PRML v0.1** schema: `--threshold-direction` becomes
the PRML `comparator`, `--dataset` becomes `dataset.id`, `--model-version`
becomes `producer.id`, and `--dataset-hash` must be a **64-char lowercase hex
SHA-256** (the old `hf:`/`sha256:`-prefixed forms are not valid PRML):

```bash
falsify-inspect lock \
  --metric accuracy \
  --threshold 0.75 \
  --threshold-direction ">=" \
  --dataset "TIGER-Lab/MMLU-Pro@527feea0afed1de15a8c115abf7be4c912123315" \
  --dataset-hash 316be51cdaf3e07bcc17fcabbab88abd7105dd5f96e02534683855fcc8cbc14a \
  --model-version openai/gpt-4o-mini \
  --sample-size 10 \
  --seed 42 \
  --task mmlu_pro_prml \
  --scorer choice \
  --claim-id "TIGER-Lab/MMLU-Pro:accuracy" \
  --output examples/mmlu_pro/claim.prml.yaml
```

The checked-in manifest hashes (canonical PRML SHA-256) to:

```text
d4a0654963f05945142f23456b455e629024b7dcfcd82c8c78b2d0ed97e1160f
```

You can re-derive it with the `falsify` reference CLI: `falsify hash
examples/mmlu_pro/claim.prml.yaml`.

## Verify the sample claim

```bash
python examples/mmlu_pro/verify_claim.py
```

The script exits with `0` when the hash matches and the observed accuracy
satisfies the pre-registered threshold.
