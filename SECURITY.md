# Security Policy

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Email **cuneyt@studio-11.co** with subject prefix `[security]`. Include:

- The vulnerable version (PyPI `falsify-inspect` version, or commit SHA)
- A reproducer if you have one
- Your assessment of impact

We aim to:

- Acknowledge within 72 hours
- Triage and confirm within 7 days
- Patch and release within 30 days for high-severity issues

If you do not receive a reply within 7 days, you may escalate by tagging
`@cuneytozturk` in a private security advisory on the falsify-inspect
repository.

## Disclosure policy

- We coordinate disclosure with the reporter
- A public advisory is published on the repository's Security tab once a
  patched version is on PyPI
- We credit reporters who consent to be named

## Scope

In scope:

- Vulnerabilities in the `falsify_inspect` package (the Python module)
- Vulnerabilities in the `falsify-inspect` CLI
- Supply-chain integrity issues affecting the published PyPI artefact

Out of scope:

- Vulnerabilities in the broader PRML specification — report those to
  the [`falsify`](https://github.com/studio-11-co/falsify) repository
- Vulnerabilities in `inspect_ai` itself — report those to the
  [Inspect AI maintainers](https://github.com/UKGovernmentBEIS/inspect_ai/security)
- Issues in third-party eval logs the package reads — those are
  Inspect-side concerns

## Supported versions

We patch the latest minor release on the `main` branch. Older versions
get backported patches only for high-severity issues.

| Version | Supported |
|---|---|
| 0.1.x | ✅ |
| < 0.1 | ❌ |

## Cryptographic claims

`falsify-inspect` computes SHA-256 hashes over canonicalised YAML bytes
per [PRML v0.1](https://spec.falsify.dev/v0.1). The cryptographic
guarantees apply only to the canonicalised bytes; if your YAML contains
non-canonical inputs (mismatched line endings, non-UTF-8 characters,
etc.) the resulting hash may not match what other PRML implementations
produce. We test against the [v0.1 conformance vectors](https://github.com/studio-11-co/falsify/tree/main/spec/test-vectors/v0.1)
on every release.

## Out-of-scope: trust assumptions

PRML's threat model (v0.1 §5) assumes:

- The publisher's hash is anchored to a verifiable timestamp
- The verifier has access to the canonical manifest bytes
- The dataset bytes are content-addressable

`falsify-inspect` inherits these assumptions. It does not defend
against:

- A publisher who anchors a hash but never publishes the manifest
- A publisher who runs the eval on a different dataset than the
  manifest commits to (closing this gap is v0.2 P-02 territory)
- Selective publication of manifests (PRML §8.1)
