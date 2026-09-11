"""Command-line interface.

    cds-audit run                     # audit every dataset (metadata + schema + preview rows)
    cds-audit run --deep              # also download files for byte-level checks
    cds-audit run --limit 36          # just the first page of recent datasets
    cds-audit run --offline --cache snapshots/2026-09-11   # re-score a saved snapshot
    cds-audit probe                   # check the API endpoints are reachable
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from . import __version__
from .client import DataSpaceClient
from .config import load_rules
from .report.html import write_html
from .report.tables import summarise, write_csv, write_issues_csv, write_json, write_markdown
from .runner import run_audit


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cds-audit", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"cds-audit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Audit datasets and write reports")
    run.add_argument("--rules", help="YAML file overriding the default rules")
    run.add_argument("--api", help="Backend base URL (default from rules.yaml)")
    run.add_argument("--out", default="reports", help="Output directory (default: reports/)")
    run.add_argument("--cache", help="Directory to store raw API responses (enables --offline re-runs)")
    run.add_argument("--offline", action="store_true", help="Use only the --cache snapshot; no network")
    run.add_argument("--limit", type=int, help="Audit at most N datasets (in 'recent' order)")
    run.add_argument("--deep", action="store_true",
                     help="Download resource files for encoding/data checks. NOTE: each download "
                          "increments the platform's download_count.")
    run.add_argument("--check-links", action="store_true", help="Request each source website to confirm it resolves")
    run.add_argument("--workers", type=int, default=4, help="Parallel dataset fetches (default 4)")
    run.add_argument("--filter", action="append", default=[], metavar="KEY=VALUE",
                     help="Extra search filter passed to the API, e.g. --filter sectors=Climate%%20Action")
    run.add_argument("--fail-under", type=float,
                     help="Exit with status 1 if the catalogue average falls below this score (for CI)")
    run.add_argument("--note", help="Banner text shown at the top of the HTML report")
    run.add_argument("-v", "--verbose", action="store_true")

    probe = sub.add_parser("probe", help="Check the API is reachable and shaped as expected")
    probe.add_argument("--rules")
    probe.add_argument("--api")
    return p


def _progress_printer():
    lock, count = threading.Lock(), [0]

    def progress(total: int, title: str) -> None:
        with lock:
            count[0] += 1
            sys.stderr.write(f"\r  audited {count[0]}/{total}  {title[:60]:<60}")
            sys.stderr.flush()
    return progress


def cmd_run(args: argparse.Namespace) -> int:
    overrides = {"api": {"base_url": args.api}} if args.api else None
    rules = load_rules(args.rules, overrides)
    if args.offline and not args.cache:
        print("--offline needs --cache <snapshot dir>", file=sys.stderr)
        return 2
    cache = args.cache or str(Path(args.out) / "snapshot")
    client = DataSpaceClient(rules["api"], cache_dir=cache, offline=args.offline)
    search_params = dict(f.split("=", 1) for f in args.filter if "=" in f)

    if args.deep and not args.offline:
        print("Deep mode: resource files will be downloaded. Each download adds to the dataset's "
              "public download count on CivicDataSpace.", file=sys.stderr)
    print(f"Auditing datasets from {rules['api']['base_url']} …", file=sys.stderr)
    audits = run_audit(client, rules, max_datasets=args.limit, deep=args.deep,
                       check_links=args.check_links, workers=args.workers,
                       progress=_progress_printer(), search_params=search_params)
    sys.stderr.write("\n")
    if not audits:
        print("No datasets returned by the search endpoint. Run `cds-audit probe` to check the API.",
              file=sys.stderr)
        return 1

    mode = "deep (files downloaded)" if args.deep else "light (metadata, schema and preview rows)"
    run_info = {"api": rules["api"]["base_url"], "mode": "deep" if args.deep else "light",
                "mode_label": mode + (" · offline snapshot" if args.offline else ""),
                "limit": args.limit, "filters": search_params, "check_links": args.check_links,
                "version": __version__, "note": args.note or ""}
    summary = summarise(audits, rules, run_info)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    site = rules["api"]["public_site"]
    write_json(audits, summary, out / "audit.json", site)
    write_csv(audits, out / "scores.csv", site)
    write_issues_csv(audits, out / "issues.csv", site)
    write_markdown(audits, summary, out / "summary.md", site)
    import json
    write_html(json.loads((out / "audit.json").read_text(encoding="utf-8")), out / "report.html")

    print(f"\n{summary['datasets']} datasets · average {summary['avg_score']} · "
          f"{summary['needs_work']} need improvement · {summary['with_fail']} fail a guideline outright")
    for g, c in summary["grades"].items():
        print(f"  {g:<18} {c}")
    print(f"\nReports written to {out.resolve()}/  (report.html, summary.md, scores.csv, issues.csv, audit.json)")
    if args.fail_under is not None and summary["avg_score"] < args.fail_under:
        print(f"Average {summary['avg_score']} is below --fail-under {args.fail_under}", file=sys.stderr)
        return 1
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    overrides = {"api": {"base_url": args.api}} if args.api else None
    rules = load_rules(args.rules, overrides)
    client = DataSpaceClient(rules["api"])
    ok = True
    print(f"Backend: {client.base}")
    try:
        hit = next(client.iter_search(max_datasets=1), None)
        print(f"  search      OK  first dataset: {hit.get('title') if hit else '(none)'}")
    except Exception as e:
        print(f"  search      FAIL {e}")
        return 1
    if hit:
        detail, errs = client.dataset_detail(str(hit["id"]))
        print(f"  getDataset  {'OK' if detail else 'FAIL'}  {'; '.join(errs)[:200]}")
        res, errs = client.dataset_resources(str(hit["id"]))
        print(f"  resources   {'OK' if not errs else 'WARN'}  {len(res)} resource(s) {'; '.join(errs)[:200]}")
        ok = bool(detail)
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if getattr(args, "verbose", False) else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "probe":
        return cmd_probe(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
