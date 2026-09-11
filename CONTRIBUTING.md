# Contributing to the DataSpace Data Ecosystem

Thank you for your interest in contributing. This project is maintained by [CivicDataLab](https://civicdatalab.in) and we welcome contributions from researchers, practitioners, and civic technologists.

---

## Ways to contribute

| Type | How |
|------|-----|
| Bug reports | Open a GitHub issue |
| New or improved audit checks (`audits/cds-audit`) | Open an issue first, then a PR with a rationale note |
| New canonical entities, or fixes to existing ones (`canonical_entities/`) | PR with the tooling and, if applicable, a sample of its output |
| Adding a new collaborative (`collaboratives/`) | See [`docs/collaboratives.md`](docs/collaboratives.md) |
| Documentation fixes | PR directly against `main` |
| Questions and partnerships | Email <info@civicdatalab.in> |

---

## Before you open a pull request

1. **Check for an open issue.** Search [existing issues](https://github.com/CivicDataLab/DataSpace-data-ecosystem/issues) before opening a new one to avoid duplication.
2. **For non-trivial changes, open an issue first.** This lets us align on scope before you invest time writing code.
3. **Reference the issue in your PR description.** Use `Closes #<issue-number>` or `Relates to #<issue-number>`.

---

## Development setup

```bash
git clone --recurse-submodules https://github.com/CivicDataLab/DataSpace-data-ecosystem.git
cd DataSpace-data-ecosystem
```

This repo has no single installable package — each part sets up independently:

- **`audits/cds-audit`** has its own `pyproject.toml`: `cd audits/cds-audit && pip install -e ".[dev]"`. See
  its own README for `cds-audit probe` / `cds-audit run` / `make demo`.
- **`canonical_entities/*/maps`** scripts install their few dependencies directly (no packaging) — see the
  README in each subdirectory.
- **`collaboratives/*`** are independent repositories; follow each one's own setup instructions.

Install the repo-wide dev tools (ruff, codespell, pre-commit) once:

```bash
pip install ruff codespell pre-commit
pre-commit install
```

---

## Submitting a pull request

1. Fork the repository and create a branch from `main`.
2. Make your changes. Keep commits focused — one logical change per commit.
3. If you touched `audits/cds-audit`, run its test suite (`cd audits/cds-audit && pytest`).
4. Open a PR against `main` with a clear title and a brief description of what changed and why.

---

## Code style

Formatting and linting are handled by [Ruff](https://docs.astral.sh/ruff/) (line length 119) and
typo-checking by [codespell](https://github.com/codespell-project/codespell), configured in the root
`pyproject.toml` and enforced in CI. `audits/cds-audit` carries its own test suite and config on top of that.

```bash
ruff format .        # auto-format
ruff check .         # lint
pre-commit run --all-files
```

- Python 3.11+.
- `collaboratives/*` are separate repositories (git submodules) — their code style is governed by their own
  repo, not this one.

---

## License

By contributing, you agree that your contributions will be licensed under the [GNU AGPL v3.0](LICENSE). Sample and derived data contributions are accepted under [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/).

By submitting a contribution, you certify that you wrote it or otherwise have the right to submit it under the project's license (see the [Developer Certificate of Origin](https://developercertificate.org/)).
