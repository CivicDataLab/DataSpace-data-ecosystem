"""Machine-readable outputs (CSV, JSON) and the Markdown summary."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

from ..models import DatasetAudit

CHECK_ORDER = [
    "1.1_title", "1.2_description", "1.3_publisher", "1.5_tags", "1.6_sectors", "1.7_geography",
    "1.8_date_of_creation", "1.9_license", "1.10_source_website",
    "2.1_file_format", "2.2_encoding", "2.3_column_naming", "2.4_data_types", "2.5_units",
    "2.6_missing_values", "2.7_data_quality", "2.8_file_naming",
]


def summarise(audits: List[DatasetAudit], rules: Dict[str, Any], run_info: Dict[str, Any]) -> Dict[str, Any]:
    """Catalogue-level numbers used by every report."""
    n = len(audits)
    grades = Counter(a.grade for a in audits)
    per_check: Dict[str, Dict[str, Any]] = {}
    for cid in CHECK_ORDER:
        rows = [c for a in audits for c in a.checks if c.check_id == cid]
        if not rows:
            continue
        st = Counter(c.status for c in rows)
        assessed = [c for c in rows if c.score is not None]
        issue_counter = Counter()
        for c in rows:
            for i in c.issues:
                issue_counter[_issue_family(i)] += 1
        per_check[cid] = {
            "guideline": rows[0].guideline,
            "weight": rows[0].weight,
            "pass": st["pass"], "warn": st["warn"], "fail": st["fail"], "na": st["na"],
            "assessed": len(assessed),
            "avg_score": round(100 * mean(c.score for c in assessed), 1) if assessed else None,
            "points_lost": round(sum(c.weight * (1 - c.score) for c in assessed), 1),
            "common_issues": issue_counter.most_common(4),
        }
    by_pub: Dict[str, List[float]] = defaultdict(list)
    for a in audits:
        by_pub[a.dataset.publisher or "(no publisher)"].append(a.score)
    publishers = sorted(
        ({"publisher": p, "datasets": len(s), "avg_score": round(mean(s), 1),
          "below_70": sum(1 for x in s if x < 70)} for p, s in by_pub.items()),
        key=lambda r: r["avg_score"],
    )
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "datasets": n,
        "avg_score": round(mean(a.score for a in audits), 1) if audits else None,
        "median_score": sorted(a.score for a in audits)[n // 2] if audits else None,
        "grades": {g["label"]: grades.get(g["label"], 0) for g in rules["grades"]},
        "needs_work": sum(1 for a in audits if a.grade != rules["grades"][0]["label"]),
        "top_grade": rules["grades"][0]["label"],
        "with_fail": sum(1 for a in audits if any(c.status == "fail" for c in a.checks)),
        "below_70": sum(1 for a in audits if a.score < 70),
        "checks": per_check,
        "publishers": publishers,
        "run": run_info,
    }


def _issue_family(issue: str) -> str:
    """Collapse dataset-specific issue text into a reusable label for counting."""
    s = re.sub(r"^\[[^\]]*\]\s*", "", issue)                  # per-resource prefix
    if re.match(r"^'[^']*'\s*—", s):                           # file-naming issues
        return "File name does not follow {theme}_{region}_{period}_v{version}"
    s = re.sub(r"^'[^']*':\s*", "", s)                          # "'column': dates not…"
    s = re.sub(r"^'[^']*'\s+(?=has )", "Column ", s)            # "'column' has percentages…"
    s = re.sub(r"\([^)]*\)", "", s)                             # parentheticals
    for cut in (" in '", " as [", " in n sampled", " e.g.", ", e.g", " — ", ": "):
        if cut in s:
            s = s.split(cut)[0]
    s = re.sub(r"'[^']*'", "", s)
    protected = {"ISO 8601": "ISO_PROTECTED_A", "0–100": "RANGE_PROTECTED_B"}
    for a, b in protected.items():
        s = s.replace(a, b)
    s = re.sub(r"(?<![\w.-])\d+(\.\d+)?(/\d+)?%?(?![\w])", "n", s)
    for a, b in protected.items():
        s = s.replace(b, a)
    s = re.sub(r"\s+([,.])", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".,")
    s = s.replace(" in n sampled", "")
    s = re.sub(r"^n\s+", "", s)                                 # "3/5 columns…" -> "columns…"
    return s[:1].upper() + s[1:]


def write_json(audits: List[DatasetAudit], summary: Dict[str, Any], path: Path, public_site: str) -> None:
    payload = {
        "summary": summary,
        "datasets": [
            {
                "id": a.dataset.id,
                "title": a.dataset.title,
                "url": a.dataset.url(public_site),
                "publisher": a.dataset.publisher,
                "sectors": a.dataset.sectors,
                "formats": sorted({r.format for r in a.dataset.resources if r.format}),
                "resources": len(a.dataset.resources),
                "modified": a.dataset.modified,
                "score": a.score,
                "grade": a.grade,
                "metadata_score": a.metadata_score,
                "data_score": a.data_score,
                "top_fixes": a.top_fixes(5),
                "fetch_errors": a.dataset.fetch_errors,
                "checks": [c.to_dict() for c in a.checks],
            }
            for a in audits
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_csv(audits: List[DatasetAudit], path: Path, public_site: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["dataset_id", "title", "url", "publisher", "score", "grade", "metadata_score", "data_score"]
                   + [f"{c}_score" for c in CHECK_ORDER] + ["top_fixes"])
        for a in audits:
            by_id = {c.check_id: c for c in a.checks}
            w.writerow([a.dataset.id, a.dataset.title, a.dataset.url(public_site), a.dataset.publisher,
                        a.score, a.grade, a.metadata_score, a.data_score]
                       + [("" if by_id.get(c) is None or by_id[c].score is None else round(100 * by_id[c].score))
                          for c in CHECK_ORDER]
                       + [" | ".join(a.top_fixes(5))])


def write_issues_csv(audits: List[DatasetAudit], path: Path, public_site: str) -> None:
    """Long format — one row per failing/warning check. Handy as a fix-it tracker."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["dataset_id", "title", "url", "publisher", "guideline", "status", "check_score",
                    "points_lost", "issues", "suggested_fix"])
        rows = []
        for a in audits:
            for c in a.checks:
                if c.score is None or c.score >= 0.999:
                    continue
                rows.append([a.dataset.id, a.dataset.title, a.dataset.url(public_site), a.dataset.publisher,
                             c.guideline, c.status, round(100 * c.score), round(c.weight * (1 - c.score), 2),
                             " | ".join(c.issues), " | ".join(c.fixes)])
        rows.sort(key=lambda r: -r[7])
        w.writerows(rows)


def write_markdown(audits: List[DatasetAudit], summary: Dict[str, Any], path: Path, public_site: str) -> None:
    s = summary
    lines = [
        "# CivicDataSpace dataset audit",
        "",
        f"Generated {s['generated_at']} · {s['datasets']} datasets · mode: {s['run'].get('mode')}",
        "",
        f"**{s['needs_work']} of {s['datasets']} datasets need improvement** (graded below {s['top_grade']}); "
        f"{s['with_fail']} fail at least one guideline outright. "
        f"Average score {s['avg_score']}, median {s['median_score']}.",
        "",
        "| Grade | Datasets |", "|---|---|",
    ]
    lines += [f"| {g} | {c} |" for g, c in s["grades"].items()]
    lines += ["", "## Where points are lost", "",
              "| Guideline | Pass | Warn | Fail | Not assessed | Avg score | Points lost |",
              "|---|---|---|---|---|---|---|"]
    for cid, c in sorted(s["checks"].items(), key=lambda kv: -kv[1]["points_lost"]):
        lines.append(f"| {c['guideline']} | {c['pass']} | {c['warn']} | {c['fail']} | {c['na']} | "
                     f"{'' if c['avg_score'] is None else c['avg_score']} | {c['points_lost']} |")
    lines += ["", "## Datasets needing the most work", ""]
    for a in audits[:15]:
        lines.append(f"### [{a.dataset.title or a.dataset.id}]({a.dataset.url(public_site)}) — {a.score} ({a.grade})")
        lines.append(f"Publisher: {a.dataset.publisher or '—'}")
        lines.append("")
        lines += [f"- {fx}" for fx in a.top_fixes(5)]
        lines.append("")
    lines += ["## By publisher", "", "| Publisher | Datasets | Avg score | Below 70 |", "|---|---|---|---|"]
    lines += [f"| {p['publisher']} | {p['datasets']} | {p['avg_score']} | {p['below_70']} |" for p in s["publishers"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
