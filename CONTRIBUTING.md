# Contributing

PRML and its reference implementations are open standards work. Issues, PRs, and design pushback are welcome.

## Quick paths

- **Found a bug:** open an issue with a minimal repro.
- **Spec-level question:** ask in [studio-11-co/falsify-hackathon discussions](https://github.com/studio-11-co/falsify-hackathon/discussions). Repo-level questions stay here.
- **Want to add code:** see `good-first-issue` and `help-wanted` labels for scoped work. For larger changes open an issue first so we can align on shape before you write a long PR.

## Pull requests

- Keep PRs small and focused. One change per PR.
- Reference the issue number in the PR body if one exists.
- Tests: add or update where relevant. CI must be green before review.
- Commit messages: imperative mood, one short summary line, optional body. No emoji.
- v0.1 conformance: any change that alters canonical-byte output must preserve byte-equivalence across the 20 conformance vectors. CI catches this.

## Code of conduct

Be direct, be technical, no harassment. Decisions on what gets merged are the maintainer's call.

## License

By contributing you agree that your work is released under the repo's stated license (see `LICENSE`).

## Maintainer

Cüneyt Öztürk — hello@falsify.dev
