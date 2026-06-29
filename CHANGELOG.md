# Changelog

All notable changes to `falsify-inspect` are documented here.

## [0.3.1] — 2026-06-29

### Fixed
- **`verify_eval_log` now works against current Inspect logs.** Inspect 0.3.x no
  longer records `eval.dataset.sha`, and `results.scores[].name` carries the
  *scorer* name, not the metric. The from-log path raised `MalformedLogError`
  (`missing fields: ['dataset_hash']`) on every modern log. `verify_eval_log`
  now accepts `dataset_hash=` and `metric=` overrides (both default to whatever
  the log carries, so older logs are unaffected), and the error message names
  exactly which fields to supply. Round-trip with `preregister` is verified.

### Added
- `examples/offline-mockllm/` — a fully offline, deterministic showcase that
  runs a real Inspect eval with `mockllm` (no API key, no network), pre-registers
  the claim, and demonstrates PASS plus a TAMPERED model-swap via `verify_live`.

## [0.3.0] — 2026-06-17

### Changed (BREAKING)
- **Migrated to the real PRML v0.1 manifest schema.** Previous releases used a
  flat, adapter-private schema (`threshold_direction`, `prml_version`, flat
  `dataset_hash`, `model_version`, `sample_size`, `pre_registered`). That schema
  was **not** valid PRML and was rejected by `falsify_prml.validate_manifest`.
  Manifests now use the nine required PRML v0.1 fields:
  `version: prml/0.1`, `claim_id`, `created_at`, `metric`, `comparator`,
  `threshold`, `dataset: {id, hash}`, `seed`, `producer: {id}`.

  Field mapping (adapter-facing arg → PRML field):
  - `threshold_direction` → `comparator`
  - `dataset` (name) → `dataset.id`
  - `dataset_hash` → `dataset.hash` (**must now be 64 lowercase hex**, a real
    SHA-256; the old `sha256:…` / `hf:…` prefixed forms are no longer valid)
  - `model_version` → `producer.id`
  - `pre_registered` → `created_at`
  - `inspect_task`, `inspect_scorer`, `sample_size` → extra top-level keys
    (PRML permits extra keys; they are still hashed)
  - new `claim_id` (defaults to `"<dataset>:<metric>"` if not supplied)
- **Hashes are now bare 64-char hex** (the canonical PRML SHA-256), not the
  previous `sha256:<hex>` prefixed form.
- **`falsify_prml` is now the engine.** The adapter no longer carries its own
  canonicalization/hashing/validation/predicate logic; all of it is delegated
  to the published `falsify` package (`falsify_prml.canonicalize`,
  `manifest_hash`, `validate_manifest`, `evaluate_predicate`). This guarantees
  byte-identical hashes with the `falsify` CLI and the JS/Go/Rust reference
  implementations.
- `load_committed_manifest()` now returns the **canonical** PRML hash of the
  parsed manifest (re-derivable on any surface), not a hash of the raw file
  bytes.
- **Verdict/receipt dicts now use PRML field names.** The verdict returned by
  `verify_live()` (and written to `*.prml-receipt.json`) no longer carries the
  legacy `threshold_direction` key — it exposes `comparator` only.
- **`verify_observation()` kwargs renamed to PRML vocabulary**: `dataset` →
  `dataset_id`, `model_version` → `producer_id`, `threshold_direction` →
  `comparator`, `pre_registered` → `created_at` (`dataset_hash` unchanged — it
  maps to the nested `dataset.hash`). The `preregister()`, `verify_eval_log()`,
  and `falsify-inspect lock/verify` CLI argument names are unchanged for
  backward compatibility.
- `extract_manifest_from_log()` now returns PRML-named keys: `producer_id` (was
  `model_version`) and `dataset_id` (was `dataset`).

### Added
- `falsify>=0.3.8` runtime dependency (ships the `falsify_prml` module).
- `--claim-id` flag on `falsify-inspect lock`.

### Migration
- Re-lock any pre-existing claims: old `.prml.yaml` files and old hashes are
  **not** compatible. Recompute the dataset hash as a 64-hex SHA-256 and re-run
  `falsify-inspect lock`. The hook (`FALSIFY_PRML`, PASS/FAIL/TAMPERED receipt,
  `FALSIFY_PRML_STRICT`) behaves the same; only the manifest schema underneath
  changed.

## [0.2.0] — 2026-06-01

### Added
- **Native Inspect AI hook (`FalsifyHooks`).** Registered via the `inspect_ai`
  setuptools entry point, so it is discovered automatically once installed
  (the same mechanism as Inspect's own MLflow / W&B example hooks). Set
  `FALSIFY_PRML=path/to/x.prml.yaml` and run `inspect eval` as usual: at each
  task end the hook reads the realised metric, checks it against the committed
  threshold, confirms the run's identity (model, dataset, task) matches the
  pre-registration, and writes a `*.prml-receipt.json` with a PASS / FAIL /
  TAMPERED verdict. Observe-only by default; set `FALSIFY_PRML_STRICT=1` to
  fail the run on a non-PASS verdict (a CI gate).
- `verify_live()` — verify a live `EvalLog` against a committed manifest in
  process (no need to write the log to disk first).
- `verify_observation()` and `load_committed_manifest()` — helpers underlying
  the hook, exported for direct use.

### Notes
- The file-based `verify_eval_log()` API and the `falsify-inspect` CLI are
  unchanged.
- `inspect_ai` remains an optional dependency; the hook is only loaded when
  running under Inspect. Verified end-to-end against a real `mockllm/model`
  eval (entry-point discovery, PASS, and TAMPERED paths).

## [0.1.0] — 2026-05-08

Initial public release.

### Added
- `preregister()` — generate a PRML manifest hash before an Inspect AI eval
- `verify_eval_log()` — re-derive the hash from an eval log + caller-supplied threshold and check
- `extract_manifest_from_log()` — pull PRML-relevant metadata out of `inspect_ai` log JSON
- `falsify-inspect lock` CLI — pre-register and emit hash
- `falsify-inspect verify` CLI — verify a log against a hash, exit 0/3/10
- 8 unit tests covering deterministic hashing, threshold validation, log extraction, pass/fail/tamper paths

### Notes
- Compatible with PRML v0.1 spec
- Inspect AI itself is an *optional* dependency — extraction works on the log JSON shape, not the live API
- Patent non-assertion grant per PRML v0.1 spec appendix
