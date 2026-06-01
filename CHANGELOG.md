# Changelog

All notable changes to `falsify-inspect` are documented here.

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
