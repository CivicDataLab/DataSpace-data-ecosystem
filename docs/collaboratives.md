# Collaboratives

Each collaborative in the CivicDataSpace ecosystem keeps its own repository — its own data, analytics
notebooks, and pipelines. This repo tracks them as git submodules under [`collaboratives/`](../collaboratives/)
so there is one place to check out to get every collaborative at once.

## Current collaboratives

| Collaborative | Repository | Path |
|---|---|---|
| FemHealth Data Collaborative | [CivicDataLab/femhealth-data-collaborative](https://github.com/CivicDataLab/femhealth-data-collaborative) | `collaboratives/femhealth-data-collaborative` |

## Cloning this repo with its collaboratives

```bash
git clone --recurse-submodules https://github.com/CivicDataLab/DataSpace-data-ecosystem.git
```

If you already cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

## Adding a new collaborative

```bash
git submodule add https://github.com/CivicDataLab/<collaborative-repo>.git collaboratives/<collaborative-repo>
```

Then add a row to the table above. Pulling in a new collaborative's history doesn't require touching anything
else in this repo — `audits/`, `data_model/`, and `canonical_entities/` are collaborative-agnostic.

## Updating a collaborative to its latest commit

```bash
git submodule update --remote collaboratives/<collaborative-repo>
git add collaboratives/<collaborative-repo>
git commit -m "Update <collaborative-repo> submodule"
```
