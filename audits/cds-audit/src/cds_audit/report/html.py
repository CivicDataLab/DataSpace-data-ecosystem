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
.errors{color:var(--fail);font-size:13px}
.guide ol{margin:0;padding-left:22px;max-width:76ch}
.guide li{margin:0 0 8px}
.guide .sub{margin:12px 0 0}
.count{color:var(--muted);font-size:13px;margin:0 0 8px}
.tag{display:inline-block;margin-left:6px;padding:0 6px;border-radius:4px;font-size:11px;font-weight:600;vertical-align:1px;white-space:nowrap}
.tag-lang{background:#e8eefc;color:#2f4a9e} .tag-ph{background:#f6d9d3;color:#8f2d1d}
.ds .gain{color:var(--pass-ink);font-weight:600;white-space:nowrap}
.todo{margin:10px 0 0;padding-left:22px;max-width:92ch}
.todo>li{margin:0 0 14px}
.todo h4{margin:0;font-size:14px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.todo h4 .gain{font-size:13px}
.todo .what{margin:3px 0 0;color:var(--muted);font-size:13px}
.todo .how{margin:3px 0 0;font-size:14px;color:var(--ink)}
.todo .what li,.todo .how li{margin:1px 0}
.todo ul{margin:2px 0 0;padding-left:18px}
.kind{background:#eef3fb;border-left:3px solid #2f4a9e;padding:8px 12px;font-size:13px;max-width:92ch;margin:8px 0}
.okline{color:var(--muted);font-size:13px;margin:14px 0 0;max-width:92ch}
details.nas{font-size:13px;color:var(--muted);margin:6px 0 0;max-width:92ch}
details.nas summary{cursor:pointer}
details.nas ul{margin:4px 0 0;padding-left:18px}
.proj{font-size:14px;margin:8px 0 0}
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

<section class="guide" id="guide">
  <h2>How to use this report</h2>
  <ol>
    <li><b>Find your datasets.</b> In <a href="#fix">Fix your datasets</a>, pick your organisation from the publisher list or search for a title. The weakest datasets are listed first.</li>
    <li><b>Open a dataset.</b> Select its row. The fixes are listed in order of the points each one recovers, so start at the top. Each fix quotes the text or file that triggered it.</li>
    <li><b>Make the changes on CivicDataSpace.</b> Metadata fixes (title, description, geography, license, source) are edits to the dataset page. Data fixes (file format, column names, units, missing values, file names) mean re-uploading the file. The next audit run picks the changes up.</li>
    <li><b>Read the grade.</b> <span id="guide-grades"></span></li>
  </ol>
  <div id="guide-notes"></div>
</section>

<section id="fix">
  <h2>Fix your datasets</h2>
  <p class="sub">Select a row to see what to change, most valuable fix first. The <i>Next fix</i> column shows the single change that recovers the most points.</p>
  <div class="controls">
    <select id="fpub" aria-label="Filter by publisher"><option value="">All publishers</option></select>
    <input id="q" type="search" placeholder="Search title or publisher" aria-label="Search datasets">
    <select id="fgrade" aria-label="Filter by grade"><option value="">All grades</option></select>
  </div>
  <p class="count" id="count"></p>
  <table class="ds" id="ds"><thead><tr>
    <th data-k="score" class="num">Score</th><th data-k="grade">Grade</th><th data-k="title">Dataset</th>
    <th data-k="publisher">Publisher</th><th>Next fix</th>
  </tr></thead><tbody></tbody></table>
</section>

<section>
  <h2>Every dataset against every guideline</h2>
  <p class="sub">Catalogue overview. Rows are datasets, weakest first, and columns follow the numbering in the uploading guidelines. Select a dataset name to jump to its fixes.</p>
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

// Guide
(function(){
  const bands = Object.keys(S.grades);
  let g = `Every dataset is scored out of 100 and graded ${esc(bands.join(", "))}, from best to worst. ` +
    `A dataset graded ${esc(S.top_grade)} meets the guidelines.`;
  if (S.grade_cap_on_fail) g += ` A dataset that fails any guideline outright is graded no higher than ${esc(S.grade_cap_on_fail)}, however high its score.`;
  if (S.grade_cap_on_placeholder_title) g += ` A dataset still carrying the platform's placeholder title (“New dataset 03 Jul 2026 - 10:01:00”) is graded no higher than ${esc(S.grade_cap_on_placeholder_title)}.`;
  $("#guide-grades").innerHTML = g;
  const notes = [];
  if (S.language_datasets) notes.push(`<b>Language datasets</b> (text and speech corpora, dictionaries, NLP and prompt datasets, marked <span class="tag tag-lang">Language</span>) describe a language, not a place or a period, so they are not asked for a geography, a time period or a year in the file name. ${S.language_datasets} datasets are treated this way. If one is classified wrongly, tell the platform team.`);
  notes.push(`Some checks (abbreviations, units, purpose and source statements) look for patterns in the text. They can flag something that is actually fine, so treat them as prompts to review.`);
  $("#guide-notes").innerHTML = notes.map(n => `<p class="sub">${n}</p>`).join("");
})();

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

// Points a check would add to the dataset's 0–100 score if fully fixed.
function gains(d){
  const assessed = d.checks.filter(c => c.score !== null && c.weight > 0);
  const total = assessed.reduce((s,c) => s + c.weight, 0) || 1;
  return assessed.filter(c => c.score < 0.999)
    .map(c => ({c, pts: 100 * c.weight * (1 - c.score) / total}))
    .sort((a,b) => b.pts - a.pts);
}
const pts = v => `+${v < 1 ? v.toFixed(1) : Math.round(v)} pts`;
const badges = d => (d.placeholder_title ? `<span class="tag tag-ph">Placeholder title</span>` : "") +
  (d.language_dataset && d.language_dataset.length ? `<span class="tag tag-lang">Language</span>` : "");

function detailHTML(d){
  const errs = d.fetch_errors && d.fetch_errors.length ? `<p class="errors">Some details could not be fetched, so a few checks may be incomplete: ${esc(d.fetch_errors.join("; "))}</p>` : "";
  const kind = d.language_dataset && d.language_dataset.length
    ? `<p class="kind">Treated as a <b>language dataset</b> (matched: ${esc(d.language_dataset.slice(0,3).join(", "))}). Geography, the time period and a year in file names are not required.</p>` : "";
  const g = gains(d);
  const todo = g.length ? `<ol class="todo">${g.map(({c, pts: p}) =>
      `<li><h4>${esc(c.guideline)} <span class="gain">${pts(p)}</span></h4>` +
      (c.issues.length ? `<div class="what">What's wrong:<ul>${c.issues.map(i => `<li>${esc(i)}</li>`).join("")}</ul></div>` : "") +
      (c.fixes.length ? `<div class="how">How to fix:<ul>${c.fixes.map(f => `<li>${esc(f)}</li>`).join("")}</ul></div>` : "") +
      `</li>`).join("")}</ol>` : `<p>Nothing to fix: this dataset meets every guideline that could be checked.</p>`;
  const top3 = g.slice(0,3).reduce((s,x) => s + x.pts, 0);
  const proj = g.length > 1 ? `<p class="proj">Score now <b>${fmt(d.score)}</b>. The first ${Math.min(3, g.length)} fixes would take it to about <b>${Math.min(100, Math.round(d.score + top3))}</b>.</p>` : "";
  const ok = d.checks.filter(c => c.status === "pass").map(c => SHORT[c.check_id] || c.guideline);
  const na = d.checks.filter(c => c.status === "na");
  return `<p><a href="${esc(d.url)}" target="_blank" rel="noopener">Open on CivicDataSpace</a> · ${d.resources} file(s)${d.formats.length ? " · " + esc(d.formats.join(", ")) : ""}${d.sectors.length ? " · " + esc(d.sectors.join(", ")) : ""}</p>` +
    errs + kind + proj + todo +
    (ok.length ? `<p class="okline">Already meets: ${esc(ok.join(", "))}.</p>` : "") +
    (na.length ? `<details class="nas"><summary>Not checked (${na.length})</summary><ul>${na.map(c => `<li>${esc(c.guideline)}: ${esc((c.evidence||{}).not_assessed || "Not assessable")}</li>`).join("")}</ul></details>` : "");
}

function renderTable(){
  const q = $("#q").value.trim().toLowerCase(), fg = $("#fgrade").value, fp = $("#fpub").value;
  const rows = P.datasets.map((d,i) => ({d,i})).filter(({d}) =>
    (!q || (d.title + " " + d.publisher).toLowerCase().includes(q)) &&
    (!fg || d.grade === fg) && (!fp || (d.publisher || "(no publisher)") === fp));
  rows.sort((a,b) => { const x = a.d[sortKey], y = b.d[sortKey];
    return (x === y ? 0 : (x ?? -1) > (y ?? -1) ? 1 : -1) * sortDir; });
  $("#count").textContent = rows.length === P.datasets.length ? `${rows.length} datasets` : `${rows.length} of ${P.datasets.length} datasets`;
  $("#ds tbody").innerHTML = rows.map(({d,i}) => {
    const top = gains(d)[0];
    const more = top ? Math.max(top.c.fixes.length, top.c.issues.length ? 1 : 0) - 1 : 0;
    const next = top ? `<b>${esc(SHORT[top.c.check_id] || top.c.guideline)}:</b> ${esc(top.c.fixes[0] || top.c.issues[0] || "")}` +
      `${more > 0 ? ` (+${more} more)` : ""} <span class="gain">${pts(top.pts)}</span>` : "—";
    return `<tr class="row" data-i="${i}" tabindex="0" aria-expanded="${openIdx===i}"><td class="num"><b>${fmt(d.score)}</b></td><td><span class="pill ${gradeCls(d.grade)}">${esc(d.grade)}</span></td>
     <td>${esc(d.title || d.id)}${badges(d)}</td><td>${esc(d.publisher || "—")}</td>
     <td class="fix">${next}</td></tr>` +
    (openIdx === i ? `<tr class="detail" id="detail-${i}"><td colspan="5">${detailHTML(d)}</td></tr>` : "");
  }).join("") ||
    `<tr><td colspan="5">No datasets match these filters. Clear the search or pick another grade.</td></tr>`;
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
