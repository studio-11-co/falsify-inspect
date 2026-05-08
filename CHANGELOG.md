# Changelog

All notable changes to `falsify-inspect` are documented here.

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
