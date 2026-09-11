"""
Configuration loading and I/O-location resolution.

Configuration is split across two TOML files in a config directory:

    scores_config.toml   one table-tree per factor
                         ([hazard.*], [exposure.*], [vulnerability.*],
                         [govtresponse.*])
    topsis_config.toml   [weights] and [classification] (required) plus the
                         optional [cumulative_vars]/[indicators]/[rounding]/
                         [derivations]/[renames] sections

There is **no** built-in default config: a config directory must be supplied
(``--config-dir`` / ``RISK_MODEL_CONFIG_DIR`` / a ``./config`` in the working
directory). Scaffold an editable one with ``drsm init-config <dir>``; the
generic templates ship as package data under ``config_templates/`` and are used
*only* by ``init_config``, never as a runtime fallback.

I/O *locations* are not configured in TOML — they come from the CLI/env via
``resolve_data_dir``/``resolve_input_file`` so that the same config can run
against data anywhere.
"""

import os
import tomllib
from importlib import resources
from pathlib import Path

# The factor names whose sections live in scores_config.toml. The shared
# [columns] table is merged into every returned config.
_SCORE_FACTORS = ("hazard", "exposure", "vulnerability", "govtresponse")
_SCORES_FILE = "scores_config.toml"
_TOPSIS_FILE = "topsis_config.toml"
_TEMPLATE_FILES = (_SCORES_FILE, _TOPSIS_FILE)


def resolve_config_dir(config_dir: str | None = None) -> Path:
    """
    Resolve the config directory, or raise if none can be found.

    Order: explicit ``config_dir`` argument, then ``RISK_MODEL_CONFIG_DIR``,
    then a ``config`` directory in the current working directory.
    """
    if config_dir:
        return Path(config_dir).resolve()
    env = os.environ.get("RISK_MODEL_CONFIG_DIR")
    if env:
        return Path(env).resolve()
    cwd_config = Path.cwd() / "config"
    if cwd_config.is_dir():
        return cwd_config
    raise FileNotFoundError(
        "no config found. Run: drsm init-config ./config (or pass --config-dir PATH, or set RISK_MODEL_CONFIG_DIR)."
    )


def _read_toml(config_dir: Path, filename: str) -> dict:
    with (config_dir / filename).open("rb") as f:
        return tomllib.load(f)


def load_config(name: str, config_dir: str | None = None) -> dict:
    """
    Load the config for one pipeline stage.

    ``name`` is one of ``hazard``, ``exposure``, ``vulnerability``,
    ``govtresponse`` or ``topsis``. Factor stages get their own ``[<name>.*]``
    subsections promoted to the top level (``cfg["inputs"]``,
    ``cfg["classification"]``, …); the topsis stage gets the contents of
    ``topsis_config.toml``. The three structural columns are not configured here
    — they are fixed names (see ``common.REQUIRED_COLUMNS``).
    """
    cfg_dir = resolve_config_dir(config_dir)

    if name == "topsis":
        return _read_toml(cfg_dir, _TOPSIS_FILE)

    scores = _read_toml(cfg_dir, _SCORES_FILE)
    if name not in _SCORE_FACTORS:
        raise ValueError(f"Unknown config section {name!r}; expected one of {', '.join((*_SCORE_FACTORS, 'topsis'))}.")
    if name not in scores:
        raise KeyError(f"Section [{name}] not found in {cfg_dir / _SCORES_FILE}.")
    return scores[name]


def init_config(dest_dir: str) -> None:
    """Scaffold an editable config directory from the bundled templates."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    existing = [f for f in _TEMPLATE_FILES if (dest / f).exists()]
    if existing:
        raise FileExistsError(
            f"{dest_dir} already contains {', '.join(existing)}; refusing to "
            f"overwrite. Remove them first or choose a different directory."
        )
    templates = resources.files("disaster_risk_score_model") / "config_templates"
    for name in _TEMPLATE_FILES:
        with (dest / name).open("wb") as f:
            f.write((templates / name).read_bytes())
    print(f"Wrote {len(_TEMPLATE_FILES)} config files to {dest_dir}")


def resolve_data_dir(data_dir: str | None = None) -> Path:
    """
    Resolve the data directory for all inputs and outputs.

    Order: explicit ``data_dir`` argument, then ``RISK_MODEL_DATA_DIR``, then
    ``./data`` in the current working directory.
    """
    if data_dir:
        return Path(data_dir).resolve()
    env = os.environ.get("RISK_MODEL_DATA_DIR")
    if env:
        return Path(env).resolve()
    return Path("data").resolve()


def resolve_input_file(input_file: str | None = None) -> str:
    """
    Resolve the master input filename (a bare name joined under the data dir).

    Order: explicit ``input_file`` argument, then ``RISK_MODEL_INPUT_FILE``,
    then ``MASTER_VARIABLES.csv``.
    """
    return input_file or os.environ.get("RISK_MODEL_INPUT_FILE") or "MASTER_VARIABLES.csv"
