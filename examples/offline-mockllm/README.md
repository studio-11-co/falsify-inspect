# Inspect AI × PRML — offline, deterministic showcase

[Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) (the UK AI Safety
Institute's eval framework) records what an evaluation *produced*. PRML records
what was *promised before it ran* — the metric, the threshold, the dataset, and
the **model identity** — sealed to a SHA-256. Run the eval on a different model
than you pre-registered, and the seal breaks: the claim reads **TAMPERED**.

This example runs a **real Inspect evaluation with the `mockllm` model**, so it
reproduces byte-for-byte on any machine with **no API key and no network**. It
uses `falsify-inspect`'s native `verify_live` path — the same one the Inspect
hook calls on `on_task_end`.

## Why model identity matters for a leaderboard

A benchmark score is only meaningful next to *which model produced it*. The
quiet gaming move is to publish a strong score and attribute it to a flagship
model, when the run was actually a different (cheaper, or differently-configured)
one. Pre-registering the claim's identity makes that substitution detectable
offline, by anyone, from the manifest alone.

## Run it

```bash
pip install -r requirements.txt
python run_showcase.py
```

## Verified output

```
==================================================================
A. Honest run -- pre-registered {accuracy >= 0.75, model mockllm}
==================================================================
locked BEFORE run   sha256=63e5ecb745b3b67f56782a166eb3249e6d0ea11d548e05f1325cc4541c06869a
  bar: accuracy >= 0.75   model=mockllm/model   dataset=584e4f442288b464...
ran Inspect (mockllm)  observed accuracy = 0.8000
verify_live -> PASS

==================================================================
B. Swapped model -- sealed for claude-3.5, but the run was mockllm
==================================================================
locked BEFORE run   sha256=18452dadcc6bcc76d16fe361e72079a73f03d4b7af00d0573ef27b4de4e046bf   (model: anthropic/claude-3.5-sonnet)
ran Inspect (mockllm)  observed accuracy = 0.8000
...the published run was actually on mockllm, not the sealed model...
verify_live -> TAMPERED   (identity does not match the sealed claim)

==================================================================
RESULT
==================================================================
A honest run    : PASS   (expected PASS)
B swapped model : TAMPERED   (expected TAMPERED)
```

Both digests (`63e5ec…`, `18452d…`) reproduce across runs — the eval is
deterministic because `mockllm` returns fixed outputs (8 of 10 correct → 0.80).

## The integration in three lines

```python
from falsify_inspect import preregister, verify_live

h, _ = preregister(metric="accuracy", threshold=0.75, threshold_direction=">=",
                   dataset="qa-toy-10", dataset_hash=DATASET_HASH,
                   model_version="mockllm/model", seed=42,
                   output_path="claim.prml.yaml")     # BEFORE the run
observed = run_your_inspect_eval()                    # Inspect, unchanged
verdict  = verify_live(manifest_path="claim.prml.yaml", observed_value=observed,
                       live_model="mockllm/model")    # AFTER -> PASS / FAIL / TAMPERED
```

In production the same check runs automatically via the `falsify_prml` Inspect
hook (`on_task_end`) when `FALSIFY_PRML` points at the committed manifest — no
glue code, the verdict lands in the eval log.

## What this does and does not prove

- **Does:** prove the eval's identity (metric, comparator, threshold, dataset,
  model, seed) was fixed before the result was known. Swapping the model — or
  any sealed field — after the fact is detectable.
- **Does not:** prove the score is correct, or that the producer ran the eval at
  all, or published every claim. PRML proves the bar was *locked*, never the
  *result*.

---

*Part of [`studio-11-co/falsify-inspect`](https://github.com/studio-11-co/falsify-inspect).
Spec: [spec.falsify.dev/v0.1](https://spec.falsify.dev/v0.1) · CC BY 4.0; code MIT.
Inspect AI is © UK AI Safety Institute, MIT — this example depends on it and is
not affiliated with or endorsed by AISI.*
