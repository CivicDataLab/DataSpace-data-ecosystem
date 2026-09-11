.PHONY: install test audit audit-deep demo

install:
	pip install -e ".[dev,deep]"

test:
	pytest -q

# Full catalogue, light mode (no file downloads). Saves a dated snapshot for offline re-runs.
audit:
	cds-audit run --out reports/$$(date +%F) --cache snapshots/$$(date +%F)

# Also downloads every file (adds to public download counts — see README).
audit-deep:
	cds-audit run --deep --out reports/$$(date +%F)-deep --cache snapshots/$$(date +%F)

# Report from the synthetic fixture snapshot — no network needed.
demo:
	python tests/make_fixtures.py
	cds-audit run --offline --deep --cache tests/fixtures/snapshot --out reports/demo \
	  --note "Demo built from synthetic fixture data. These are not real CivicDataSpace datasets."
