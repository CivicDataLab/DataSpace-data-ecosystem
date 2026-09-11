"""Self-contained, offline HTML report (no CDN, no external assets)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

SHORT = {
    "1.1_title": "Title", "1.2_description": "Description", "1.3_publisher": "Publisher",
    "1.5_tags": "Tags", "1.6_sectors": "Sectors", "1.7_geography": "Geography",
    "1.8_date_of_creation": "Created date", "1.9_license": "License", "1.10_source_website": "Source link",
    "2.1_file_format": "File format", "2.2_encoding": "Encoding", "2.3_column_naming": "Column names",
    "2.4_data_types": "Data types", "2.5_units": "Units", "2.6_missing_values": "Missing values",
    "2.7_data_quality": "Quality", "2.8_file_naming": "File name",
}


def write_html(json_payload: Dict[str, Any], path: Path) -> None:
    data = json.dumps({"payload": json_payload, "short": SHORT}, ensure_ascii=False, default=str)
    data = data.replace("</", "<\\/")
    path.write_text(TEMPLATE.replace("/*__DATA__*/", data), encoding="utf-8")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CivicDataSpace dataset audit</title>
<style>
:root{
  --ink:#0b3865; --text:#1c2733; --muted:#5b6875; --paper:#f5f7f9; --surface:#fff;
  --line:#dfe4e9; --pass:#84dccf; --pass-ink:#1f7a70; --warn:#fdb557; --warn-ink:#8a5a12;
  --fail:#c9513d; --na:#e6eaee; --focus:#3e63dd;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--text);
  font:15px/1.55 Inter,"Segoe UI",system-ui,-apple-system,sans-serif;font-feature-settings:"tnum" 1}
a{color:var(--ink)}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.wrap{max-width:1180px;margin:0 auto;padding:40px 28px 80px}
header .meta{color:var(--muted);font-size:13px}
.note{background:#fff4e0;border-left:4px solid var(--warn);padding:10px 14px;margin:0 0 24px;font-size:14px;max-width:70ch}
header .brand{font-weight:600;color:var(--ink);font-size:15px;margin-bottom:28px}
h1{font-size:40px;line-height:1.12;letter-spacing:-.02em;color:var(--ink);margin:0 0 14px;max-width:22ch;font-weight:700}
.lede{font-size:17px;max-width:66ch;margin:0 0 8px}
.grades{display:flex;gap:18px;flex-wrap:wrap;margin:18px 0 0;font-size:14px}
.grades span b{font-size:19px;color:var(--ink);margin-right:4px}
h2{font-size:22px;color:var(--ink);margin:64px 0 6px;letter-spacing:-.01em}
.sub{color:var(--muted);margin:0 0 20px;max-width:70ch;font-size:14px}

/* Guideline grid — the centrepiece */
.gridbox{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:18px 18px 12px;overflow:auto;max-height:78vh}
table.grid{border-collapse:separate;border-spacing:3px;font-size:13px}
.grid th.col{height:118px;vertical-align:bottom;padding:0;width:24px;min-width:24px}
.grid th.col div{transform:rotate(-58deg);transform-origin:left bottom;white-space:nowrap;width:24px;
  margin-left:14px;color:var(--muted);font-weight:500;font-size:12px}
.grid thead tr:last-child th.col{background:transparent}
.grid thead tr:last-child{background:var(--surface)}
.grid th.col.gap{width:10px;min-width:10px}
.grid thead th{position:sticky;top:-18px;background:var(--surface);z-index:2}
.grid .name{position:sticky;left:-18px;background:var(--surface);z-index:1;text-align:left;font-weight:400;
  padding:0 12px 0 0;white-space:nowrap;width:340px;min-width:340px;max-width:340px}
.grid .name button{all:unset;cursor:pointer;display:inline-block;max-width:286px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom}
.grid .name button:focus-visible{outline:2px solid var(--focus)}
.grid .name button:hover{text-decoration:underline}
.grid .name .sc{display:inline-block;width:34px;color:var(--muted);text-align:right;margin-right:10px}
.cell{width:24px;height:22px;border-radius:4px;display:block}
.s-pass{background:var(--pass)} .s-warn{background:var(--warn)} .s-fail{background:var(--fail)} .s-na{background:var(--na)}
.legend{display:flex;gap:18px;font-size:13px;color:var(--muted);margin:12px 0 0;flex-wrap:wrap}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.grouphead th{font-size:12px;color:var(--muted);font-weight:600;text-align:left;padding-bottom:2px}

/* Where points are lost */
.losses{display:grid;grid-template-columns:minmax(170px,230px) 1fr minmax(0,340px);gap:10px 18px;align-items:center}
.losses .g{font-weight:500}
.losses .g small{display:block;color:var(--muted);font-weight:400}
.bar{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--na)}
.bar span{display:block;height:100%}
.losses .why{font-size:13px;color:var(--muted)}

/* Dataset table */
.controls{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 14px}
.controls input,.controls select{font:inherit;font-size:14px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--text)}
.controls input{flex:1;min-width:220px}
table.ds{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:14px}
.ds th{text-align:left;font-weight:600;color:var(--muted);font-size:13px;padding:10px 12px;border-bottom:1px solid var(--line);cursor:pointer;user-select:none;white-space:nowrap}
.ds td{padding:10px 12px;border-bottom:1px solid #eef1f4;vertical-align:top}
.ds tr.row{cursor:pointer}
.ds tr.row:hover td{background:#f9fbfc}
.ds .num{text-align:right;white-space:nowrap}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.g-Good{background:#d8f3ee;color:var(--pass-ink)} .g-Fair{background:#e8eefc;color:#2f4a9e}
.g-Needs{background:#feecd0;color:var(--warn-ink)} .g-Poor{background:#f6d9d3;color:#8f2d1d}
.ds .fix{color:var(--muted);font-size:13px}
tr.detail td{background:#fbfcfd;padding:6px 16px 22px}
.checks{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:4px 28px;margin-top:8px}
.chk{padding:8px 0;border-bottom:1px solid #eef1f4}
.chk h4{margin:0;font-size:14px;font-weight:600;display:flex;gap:8px;align-items:center}
.chk h4 .dot{width:10px;height:10px;border-radius:50%;flex:none}
.chk h4 .pts{margin-left:auto;color:var(--muted);font-weight:400;font-size:13px}
.chk ul{margin:4px 0 0;padding-left:18px;font-size:13px}
.chk .fx{color:var(--ink)}
.chk .na{color:var(--muted);font-size:13px;margin:2px 0 0}
.errors{color:var(--fail);font-size:13px}
.pub{width:100%;max-width:720px}
footer{margin-top:64px;color:var(--muted);font-size:13px;max-width:78ch}
footer code{font-size:12px}
@media (max-width:760px){h1{font-size:30px}.grid .name{width:200px;min-width:200px;max-width:200px}.grid .name button{max-width:150px}.losses{grid-template-columns:1fr}.losses .why{margin-bottom:10px}}
@media print{.controls{display:none}.gridbox{max-height:none}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="brand">CivicDataSpace · dataset audit</div>
  <p class="note" id="note" hidden></p>
  <h1 id="verdict"></h1>
  <p class="lede" id="lede"></p>
  <div class="grades" id="grades"></div>
  <p class="meta" id="meta"></p>
</header>

<section>
  <h2>Every dataset against every guideline</h2>
  <p class="sub">Rows are datasets, weakest first. Columns follow the numbering in the uploading guidelines. Select a dataset name to see what to fix.</p>
  <div class="gridbox"><table class="grid" id="grid"></table></div>
  <div class="legend">
    <span><i class="s-pass"></i>Meets the guideline</span>
    <span><i class="s-warn"></i>Partly meets</span>
    <span><i class="s-fail"></i>Does not meet</span>
    <span><i class="s-na"></i>Not assessable from available data</span>
  </div>
</section>

<section>
  <h2>Where the catalogue loses points</h2>
  <p class="sub">Guidelines ordered by total weighted points lost across all datasets, with the most frequent problem behind each.</p>
  <div class="losses" id="losses"></div>
</section>

<section>
  <h2>Datasets</h2>
  <p class="sub">Select a row for the check-by-check breakdown and suggested fixes.</p>
  <div class="controls">
    <input id="q" type="search" placeholder="Search title or publisher" aria-label="Search datasets">
    <select id="fgrade" aria-label="Filter by grade"><option value="">All grades</option></select>
    <select id="fpub" aria-label="Filter by publisher"><option value="">All publishers</option></select>
  </div>
  <table class="ds" id="ds"><thead><tr>
    <th data-k="score" class="num">Score</th><th data-k="grade">Grade</th><th data-k="title">Dataset</th>
    <th data-k="publisher">Publisher</th><th data-k="metadata_score" class="num">Metadata</th>
    <th data-k="data_score" class="num">Data</th><th>Most valuable fix</th>
  </tr></thead><tbody></tbody></table>
</section>

<section>
  <h2>Publishers</h2>
  <p class="sub">Average score of each publisher's datasets — useful for deciding who to contact first.</p>
  <table class="ds pub" id="pubs"><thead><tr><th>Publisher</th><th class="num">Datasets</th><th class="num">Average</th><th class="num">Below 70</th></tr></thead><tbody></tbody></table>
</section>

<footer id="foot"></footer>
</div>

<script>
const D = /*__DATA__*/;
const P = D.payload, S = P.summary, SHORT = D.short;
const ORDER = Object.keys(SHORT);
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const gradeCls = g => "g-" + String(g).split(" ")[0];
const fmt = v => v === null || v === undefined ? "—" : Math.round(v);

// Header
if (S.run.note) { $("#note").textContent = S.run.note; $("#note").hidden = false; }
$("#verdict").textContent = S.needs_work
  ? `${S.needs_work} of ${S.datasets} datasets fall short of the uploading guidelines.`
  : `All ${S.datasets} datasets meet the uploading guidelines.`;
$("#lede").textContent = `${S.with_fail} fail at least one guideline outright. The average dataset scores ${S.avg_score} out of 100 ` +
  `(median ${S.median_score}). A dataset is graded ${S.top_grade} only when it scores 85 or more and fails no guideline.`;
$("#grades").innerHTML = Object.entries(S.grades).map(([g,c]) => `<span><b>${c}</b>${esc(g)}</span>`).join("");
$("#meta").textContent = `Generated ${S.generated_at} from ${S.run.api || ""} · ${S.run.mode_label || ""}`;

// Grid
(function(){
  const meta = ORDER.filter(k => k.startsWith("1.")), data = ORDER.filter(k => k.startsWith("2."));
  let h = `<thead><tr class="grouphead"><th></th><th colspan="${meta.length}">Metadata</th><th></th><th colspan="${data.length}">Data</th></tr><tr><th class="name" style="z-index:70"></th>`;
  let zi = 60;
  meta.forEach(k => h += `<th class="col" style="z-index:${zi--}" title="${esc(k.replace('_',' '))}"><div>${k.split('_')[0]} ${esc(SHORT[k])}</div></th>`);
  h += `<th class="col gap" style="z-index:${zi--}"></th>`;
  data.forEach(k => h += `<th class="col" style="z-index:${zi--}" title="${esc(k.replace('_',' '))}"><div>${k.split('_')[0]} ${esc(SHORT[k])}</div></th>`);
  h += `</tr></thead><tbody>`;
  P.datasets.forEach((d, i) => {
    const by = Object.fromEntries(d.checks.map(c => [c.check_id, c]));
    h += `<tr><th class="name"><span class="sc">${fmt(d.score)}</span><button data-i="${i}" title="${esc(d.title)}">${esc(d.title || d.id)}</button></th>`;
    const cell = k => { const c = by[k]; if (!c) return `<td></td>`;
      const tip = `${SHORT[k]}: ${c.status}` + (c.issues.length ? " — " + c.issues.slice(0,2).join(" / ") : (c.evidence && c.evidence.not_assessed ? " — " + c.evidence.not_assessed : ""));
      return `<td><span class="cell s-${c.status}" title="${esc(tip)}"></span></td>`; };
    meta.forEach(k => h += cell(k)); h += `<td></td>`; data.forEach(k => h += cell(k));
    h += `</tr>`;
  });
  $("#grid").innerHTML = h + `</tbody>`;
  $("#grid").addEventListener("click", e => { const b = e.target.closest("button[data-i]"); if (b) openDetail(+b.dataset.i); });
})();

// Losses
(function(){
  const rows = Object.entries(S.checks).sort((a,b) => b[1].points_lost - a[1].points_lost);
  $("#losses").innerHTML = rows.map(([k,c]) => {
    const tot = c.pass + c.warn + c.fail + c.na || 1;
    const seg = (n, cls) => n ? `<span class="${cls}" style="width:${100*n/tot}%" title="${n}"></span>` : "";
    const why = c.common_issues.length ? `${esc(c.common_issues[0][0])} (${c.common_issues[0][1]})` : "No recurring issue";
    return `<div class="g">${esc(c.guideline)}<small>${c.fail} fail · ${c.warn} partial · ${c.pass} pass${c.na ? " · " + c.na + " not assessed" : ""}</small></div>
      <div class="bar" role="img" aria-label="${c.pass} pass, ${c.warn} partial, ${c.fail} fail">${seg(c.pass,"s-pass")}${seg(c.warn,"s-warn")}${seg(c.fail,"s-fail")}${seg(c.na,"s-na")}</div>
      <div class="why">${why}</div>`;
  }).join("");
})();

// Dataset table
let sortKey = "score", sortDir = 1, openIdx = null;
const grades = [...new Set(P.datasets.map(d => d.grade))];
grades.forEach(g => $("#fgrade").insertAdjacentHTML("beforeend", `<option>${esc(g)}</option>`));
[...new Set(P.datasets.map(d => d.publisher || "(no publisher)"))].sort()
  .forEach(p => $("#fpub").insertAdjacentHTML("beforeend", `<option>${esc(p)}</option>`));

function detailHTML(d){
  const errs = d.fetch_errors && d.fetch_errors.length ? `<p class="errors">API errors: ${esc(d.fetch_errors.join("; "))}</p>` : "";
  const checks = d.checks.map(c => {
    const lost = c.score === null ? "" : `${(c.weight*(1-c.score)).toFixed(1)} of ${c.weight} pts lost`;
    const body = c.status === "na" ? `<p class="na">${esc((c.evidence||{}).not_assessed || "Not assessed")}</p>`
      : (c.issues.length ? `<ul>${c.issues.map(i => `<li>${esc(i)}</li>`).join("")}${c.fixes.map(f => `<li class="fx">Fix: ${esc(f)}</li>`).join("")}</ul>` : "");
    return `<div class="chk"><h4><span class="dot s-${c.status}"></span>${esc(c.guideline)}<span class="pts">${c.status === "pass" ? "" : lost}</span></h4>${body}</div>`;
  }).join("");
  return `<p><a href="${esc(d.url)}" target="_blank" rel="noopener">Open on CivicDataSpace</a> · ${d.resources} file(s)${d.formats.length ? " · " + esc(d.formats.join(", ")) : ""}${d.sectors.length ? " · " + esc(d.sectors.join(", ")) : ""}</p>${errs}<div class="checks">${checks}</div>`;
}

function renderTable(){
  const q = $("#q").value.trim().toLowerCase(), fg = $("#fgrade").value, fp = $("#fpub").value;
  const rows = P.datasets.map((d,i) => ({d,i})).filter(({d}) =>
    (!q || (d.title + " " + d.publisher).toLowerCase().includes(q)) &&
    (!fg || d.grade === fg) && (!fp || (d.publisher || "(no publisher)") === fp));
  rows.sort((a,b) => { const x = a.d[sortKey], y = b.d[sortKey];
    return (x === y ? 0 : (x ?? -1) > (y ?? -1) ? 1 : -1) * sortDir; });
  $("#ds tbody").innerHTML = rows.map(({d,i}) =>
    `<tr class="row" data-i="${i}" tabindex="0" aria-expanded="${openIdx===i}"><td class="num"><b>${fmt(d.score)}</b></td><td><span class="pill ${gradeCls(d.grade)}">${esc(d.grade)}</span></td>
     <td>${esc(d.title || d.id)}</td><td>${esc(d.publisher || "—")}</td><td class="num">${fmt(d.metadata_score)}</td><td class="num">${fmt(d.data_score)}</td>
     <td class="fix">${esc((d.top_fixes[0] || "").replace(/^\[[^\]]+\]\s*/, ""))}</td></tr>` +
    (openIdx === i ? `<tr class="detail" id="detail-${i}"><td colspan="7">${detailHTML(d)}</td></tr>` : "")).join("") ||
    `<tr><td colspan="7">No datasets match these filters. Clear the search or pick another grade.</td></tr>`;
}
function openDetail(i){
  openIdx = openIdx === i ? null : i;
  $("#q").value = ""; $("#fgrade").value = ""; $("#fpub").value = "";
  renderTable();
  const el = document.getElementById("detail-" + i);
  if (el) el.previousElementSibling.scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start"});
}
$("#ds tbody").addEventListener("click", e => { const r = e.target.closest("tr.row"); if (r && !e.target.closest("a")) { openIdx = openIdx === +r.dataset.i ? null : +r.dataset.i; renderTable(); }});
$("#ds tbody").addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { const r = e.target.closest("tr.row"); if (r) { e.preventDefault(); openIdx = openIdx === +r.dataset.i ? null : +r.dataset.i; renderTable(); document.querySelector(`tr.row[data-i="${r.dataset.i}"]`).focus(); }}});
document.querySelectorAll("#ds th[data-k]").forEach(th => th.addEventListener("click", () => {
  const k = th.dataset.k; sortDir = sortKey === k ? -sortDir : 1; sortKey = k; renderTable(); }));
["#q","#fgrade","#fpub"].forEach(s => $(s).addEventListener("input", renderTable));
renderTable();

// Publishers
$("#pubs tbody").innerHTML = S.publishers.map(p =>
  `<tr><td>${esc(p.publisher)}</td><td class="num">${p.datasets}</td><td class="num">${p.avg_score}</td><td class="num">${p.below_70}</td></tr>`).join("");

// Footer
const w = Object.entries(S.checks).map(([k,c]) => `${k.split("_")[0]} ${SHORT[k]} ${c.weight}`).join(", ");
$("#foot").innerHTML = `<p><b>How scores work.</b> Each guideline is checked automatically and scored 0–1, then weighted (${esc(w)}). ` +
  `Checks with nothing to assess (for example, encoding without the raw file) are left out of that dataset's total rather than counted against it. ` +
  `Grades: ${esc(Object.keys(S.grades).join(", "))}.</p>` +
  `<p>Heuristic checks — abbreviations, units, purpose statements — flag likely problems for a person to confirm; treat them as prompts, not verdicts.</p>` +
  `<p>Mode: ${esc(S.run.mode_label || "")}. Full check-level data is in <code>audit.json</code> and <code>issues.csv</code>.</p>`;
</script>
</body>
</html>
"""
