"""Load and merge audit rules."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "rules.yaml"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_rules(path: Optional[str] = None, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load the bundled rules.yaml, optionally merged with a user file and CLI overrides."""
    with open(DEFAULT_RULES_PATH, encoding="utf-8") as fh:
        rules = yaml.safe_load(fh)
    if path and Path(path).resolve() != DEFAULT_RULES_PATH:
        with open(path, encoding="utf-8") as fh:
            rules = _deep_merge(rules, yaml.safe_load(fh) or {})
    if overrides:
        rules = _deep_merge(rules, overrides)
    return rules
