# Contributing to IDS-DRR Risk Score Model

Thank you for your interest in contributing. This project is maintained by [CivicDataLab](https://civicdatalab.in) and we welcome contributions from researchers, practitioners, and civic technologists.

---

## Ways to contribute

| Type | How |
|------|-----|
| Bug reports | Open a GitHub issue |
| Methodology improvements | Open an issue first, then a PR with a rationale note |
| New geography adaptations | Share config files and a brief validation summary |
| Documentation fixes | PR directly against `main` |
| Questions and partnerships | Email <info@civicdatalab.in> |

---

## Before you open a pull request

1. **Check for an open issue.** Search [existing issues](https://github.com/CivicDataLab/risk-score-model-generic/issues) before opening a new one to avoid duplication.
2. **For non-trivial changes, open an issue first.** This lets us align on scope before you invest time writing code.
3. **Reference the issue in your PR description.** Use `Closes #<issue-number>` or `Relates to #<issue-number>`.

---

## Development setup

```bash
git clone https://github.com/CivicDataLab/risk-score-model-generic.git
cd risk-score-model-generic
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .[dev]
```

Run the model end-to-end against synthetic sample data to confirm your environment is working:

```bash
drsm init-config ./config
drsm generate-sample-data
drsm run
```

---

## Submitting a pull request

1. Fork the repository and create a branch from `main`.
2. Make your changes. Keep commits focused — one logical change per commit.
3. Confirm that the end-to-end pipeline still produces output without errors.
4. Open a PR against `main` with a clear title and a brief description of what changed and why.

---

## Proposing methodological changes

The scoring methodology (factor weights, normalisation approach, DEA setup, TOPSIS aggregation) has implications for operational decisions downstream. Before proposing a change:

- Attach a short note explaining the rationale — what problem does the change address?
- Where possible, cite empirical evidence or literature that supports the change.
- If the change affects numerical outputs, include a comparison of scores before and after (even on the sample dataset) so reviewers can assess the magnitude.

---

## Code style

We follow the [OCP Software Development Handbook](https://ocp-software-handbook.readthedocs.io/en/latest/python/index.html).
Formatting and linting are handled by [Ruff](https://docs.astral.sh/ruff/) (line
length 119) and typo-checking by [codespell](https://github.com/codespell-project/codespell),
all configured in `pyproject.toml` and enforced in CI.

Install the hooks once after setting up your environment so checks run on every commit:

```bash
pre-commit install
```

Run the checks manually at any time:

```bash
ruff format .        # auto-format
ruff check .         # lint
pre-commit run --all-files
```

- Python 3.11+.
- Avoid adding dependencies not declared in `pyproject.toml` without discussion.
- Configuration changes (new variables, thresholds, factor input column names) belong in TOML config files, not hardcoded in scripts. The three structural columns (`time_period`, `unit_id`, `parent_unit`) are the exception — they are fixed required names, not configurable.

---

## Naming conventions

A single convention keeps the data dictionary, configs, and outputs consistent —
important for a machine-readable Digital Public Good.

- **Inputs, config keys, intermediate columns, and Python identifiers use
  `snake_case`** — lowercase words separated by underscores (e.g.
  `total_population`, `net_sown_area_ha`, `flood_protection_failures`). Avoid
  spaces, capitals, and unexplained abbreviations in column names.
- **Output / platform-display columns use `kebab-case`** — lowercase words
  separated by hyphens (e.g. `flood-hazard`, `risk-score`,
  `total-population`). The TOPSIS step produces these automatically by applying
  `name.lower().replace("_", "-").replace(" ", "-")` to every column, so a
  well-named `snake_case` input maps cleanly to its `kebab-case` output.
- **`docs/data_dictionary.csv` is the authoritative list of column slugs.**
  When you add, remove, or rename a column, update the dictionary in the same PR
  so the schema contract stays accurate.
- **Keep geography-specific names out of the generic core** (the
  `disaster_risk_score_model/` library and its bundled config templates).
  Anything specific to one jurisdiction — scheme acronyms,
  local administrative units, display-only derivations — belongs in that
  geography's config under `contrib/` (see the `[derivations]` and `[renames]`
  sections used by `contrib/india/example/`).

---

## License

By contributing, you agree that your contributions will be licensed under the [GNU AGPL v3.0](LICENSE). Sample and derived data contributions are accepted under [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/).

By submitting a contribution, you certify that you wrote it or otherwise have the right to submit it under the project's license (see the [Developer Certificate of Origin](https://developercertificate.org/)).

