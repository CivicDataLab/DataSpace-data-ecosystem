import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from cds_audit.config import load_rules  # noqa: E402

SNAPSHOT = ROOT / "tests" / "fixtures" / "snapshot"


@pytest.fixture(scope="session")
def rules():
    return load_rules()


@pytest.fixture(scope="session")
def snapshot():
    if not (SNAPSHOT / "search_page-1_size-36_sort-recent.json").exists():
        import make_fixtures
        make_fixtures.build()
    return SNAPSHOT
