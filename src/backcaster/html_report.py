"""Self-contained HTML projection reports, with no network assets."""

from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd

from backcaster.stat_columns import BATTING_STAT_COLUMNS, IDENTITY_COLUMNS, PITCHING_STAT_COLUMNS

BATTING_COLUMNS = (*BATTING_STAT_COLUMNS, "Reliability")
PITCHING_COLUMNS = (*PITCHING_STAT_COLUMNS, "Reliability")
COLUMN_LABELS = {"PlayerID": "Player ID"}
COLUMN_HELP = {
    "IP": "Innings in baseball notation: .1 = one out, .2 = two outs",
    "Reliability": "Observed-evidence weight; not a probability of prediction accuracy",
    "Age": "Projection year minus birth year",
}

REPORT_CSS = r"""
:root { --brand:#153e3b; --brand-dark:#102e2c; --accent:#78bd82; --canvas:#f3f6f5; --surface:#fff; --ink:#183634; --muted:#617571; --line:#dce5e2; --stripe:#f8faf9; --radius:12px; }
* { box-sizing:border-box; }
body { margin:0; background:var(--canvas); color:var(--ink); font:14px/1.5 'Segoe UI',system-ui,sans-serif; }
.topbar { background:var(--brand-dark); color:white; padding:18px 32px; display:flex; align-items:center; justify-content:space-between; gap:20px; }
.brand { font-size:19px; font-weight:700; letter-spacing:-.4px; }
.brand-mark { display:inline-block; width:12px; height:12px; background:var(--accent); border-radius:3px; transform:rotate(-15deg); margin-right:11px; }
.topbar small { color:#bcd4cb; letter-spacing:.08em; font-size:11px; }
main { max-width:1720px; margin:auto; padding:32px; }
.eyebrow { color:var(--muted); font-weight:700; letter-spacing:.13em; text-transform:uppercase; font-size:11px; margin:0 0 7px; }
h1 { font-size:30px; line-height:1.2; margin:0 0 10px; font-weight:650; letter-spacing:-.8px; }
.subtitle { color:var(--muted); margin:0; }
.intro { margin-bottom:24px; }
.cards { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; margin-bottom:26px; }
.card { background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:18px 22px; border-top:3px solid var(--accent); }
.card-label { color:var(--muted); font-size:12px; margin-bottom:4px; }
.card-value { font-size:25px; font-weight:650; letter-spacing:-.5px; overflow-wrap:anywhere; }
.card-note { color:var(--muted); font-size:11px; margin-top:3px; }
.panel { border:1px solid var(--line); border-radius:var(--radius); background:white; overflow:hidden; box-shadow:0 3px 14px #18363405; }
.toolbar { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:14px; padding:20px; border-bottom:1px solid var(--line); }
h2 { margin:0; font-size:16px; font-weight:650; }
.table-hint { margin:3px 0 0; color:var(--muted); font-size:12px; }
.controls { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
label { font-size:12px; font-weight:600; }
input { border:1px solid #baccc6; border-radius:7px; padding:9px 11px; font:inherit; width:245px; background:#fff; }
button { cursor:pointer; font:inherit; }
.action { border:1px solid #baccc6; border-radius:7px; padding:9px 13px; background:white; color:var(--brand); font-weight:600; font-size:12px; }
.action.primary { background:var(--brand); border-color:var(--brand); color:white; }
button:hover { filter:brightness(.95); }
input:focus,button:focus-visible,.table-scroll:focus-visible { outline:3px solid #78bd82; outline-offset:2px; }
.table-scroll { overflow:auto; max-height:70vh; }
table { border-collapse:separate; border-spacing:0; min-width:100%; width:max-content; font-size:12px; font-variant-numeric:tabular-nums; }
caption { text-align:left; padding:0; }
.sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
th,td { padding:11px 13px; white-space:nowrap; text-align:right; border-bottom:1px solid #eaf0ed; }
th { position:sticky; top:0; background:#eaf0ed; color:#49605b; z-index:2; font-size:11px; letter-spacing:.02em; }
th button { background:none; color:inherit; border:0; padding:0; font-weight:700; white-space:nowrap; }
th button::after { content:' ↕'; opacity:.4; font-weight:400; }
th[aria-sort=ascending] button::after { content:' ↑'; opacity:1; }
th[aria-sort=descending] button::after { content:' ↓'; opacity:1; }
td:first-child,th:first-child { text-align:left; position:sticky; left:0; }
td:first-child { background:inherit; font-weight:600; z-index:1; min-width:175px; }
th:first-child { z-index:3; }
td:nth-child(3),th:nth-child(3) { text-align:left; }
td:nth-child(3) { font-family:ui-monospace,Consolas,monospace; font-size:11px; color:var(--muted); }
tbody tr { background:white; }
tbody tr:nth-child(even) { background:var(--stripe); }
tbody tr:hover { background:#eaf5ed; }
.rate { color:var(--brand); font-weight:650; background-color:#78bd8209; }
.table-footer { padding:12px 20px; font-size:12px; color:var(--muted); display:flex; justify-content:space-between; gap:16px; border-top:1px solid var(--line); }
.report-notes { display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-top:22px; color:var(--muted); font-size:12px; }
.report-notes strong { display:block; color:var(--ink); margin-bottom:4px; font-weight:600; }
footer { display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-top:28px; padding-top:16px; border-top:1px solid var(--line); font-size:11px; color:var(--muted); }
.empty { text-align:center; padding:28px; color:var(--muted); }
[hidden] { display:none!important; }
@media(max-width:700px) { main { padding:20px 12px; } .topbar { padding:16px; } .cards { grid-template-columns:1fr; gap:10px; } .card { padding:12px 16px; } .card-value { font-size:21px; } h1 { font-size:25px; } .report-notes { grid-template-columns:1fr; } input { width:190px; } }
@page { size:landscape; margin:12mm; }
@media print { body { background:white; font-size:10px; } .topbar { background:white; color:var(--ink); padding:0 0 12px; border-bottom:2px solid var(--brand); } .topbar small { color:var(--muted); } main { padding:18px 0; max-width:none; } .controls,.table-hint { display:none; } .cards { gap:10px; margin-bottom:14px; } .card { padding:10px; } .panel { box-shadow:none; overflow:visible; } .table-scroll { overflow:visible; max-height:none; } table { width:100%; min-width:0; font-size:8px; } th,td { padding:5px 4px; position:static!important; } td:first-child { min-width:0; } thead { display:table-header-group; } tr { break-inside:avoid; } .report-notes { font-size:9px; } }
"""

REPORT_JS = r"""
(() => {
 const table=document.getElementById('projections');
 const body=table.tBodies[0];
 const rows=Array.from(body.querySelectorAll('tr[data-player]'));
 const search=document.getElementById('search');
 const status=document.getElementById('visible-count');
 const empty=document.getElementById('no-matches');
 let active=-1, ascending=true;
 function filter() {
   const query=search.value.trim().toLocaleLowerCase();
   let visible=0;
   rows.forEach(row=>{row.hidden=!row.textContent.toLocaleLowerCase().includes(query); if(!row.hidden)visible++;});
   status.textContent=`Showing ${visible} of ${rows.length} players`;
   empty.hidden=visible!==0;
 }
 table.querySelectorAll('thead button').forEach((button,index)=>{
   button.addEventListener('click',()=>{
     ascending=active===index?!ascending:true; active=index;
     const sorted=[...rows].sort((a,b)=>{
       const x=a.cells[index].textContent.trim(), y=b.cells[index].textContent.trim();
       const numeric=x!==''&&y!==''&&Number.isFinite(Number(x))&&Number.isFinite(Number(y));
       return (numeric?Number(x)-Number(y):x.localeCompare(y,undefined,{numeric:true}))*(ascending?1:-1);
     });
     table.querySelectorAll('th').forEach(th=>th.setAttribute('aria-sort','none'));
     button.parentElement.setAttribute('aria-sort',ascending?'ascending':'descending');
     sorted.forEach(row=>body.appendChild(row)); filter();
   });
 });
 search.addEventListener('input',filter);
 document.getElementById('reset').addEventListener('click',()=>{
   search.value='';active=-1;ascending=true;rows.forEach(row=>body.appendChild(row));
   table.querySelectorAll('th').forEach(th=>th.setAttribute('aria-sort','none'));filter();
 });
 document.getElementById('print').addEventListener('click',()=>window.print());
 filter();
})();
"""


def _cell(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _table(frame: pd.DataFrame, columns: list[str]) -> str:
    headers = []
    for column in columns:
        label = escape(COLUMN_LABELS.get(column, column))
        title = escape(
            COLUMN_HELP.get(column, f"Sort by {COLUMN_LABELS.get(column, column)}"), quote=True
        )
        headers.append(
            f'<th scope="col" aria-sort="none"><button type="button" title="{title}">{label}</button></th>'
        )
    rows = []
    for row in frame.itertuples(index=False, name=None):
        cells = []
        for column, value in zip(columns, row):
            style = (
                ' class="rate"'
                if column
                in {
                    "BA",
                    "AVG",
                    "OBP",
                    "SLG",
                    "OPS",
                    "W-L%",
                    "ERA",
                    "WHIP",
                    "H9",
                    "HR9",
                    "BB9",
                    "SO9",
                    "SO/W",
                }
                else ""
            )
            cells.append(f"<td{style}>{escape(_cell(value))}</td>")
        rows.append('<tr data-player="true">' + "".join(cells) + "</tr>")
    return (
        '<table id="projections"><caption class="sr-only">Player projection statistics</caption><thead><tr>'
        + "".join(headers)
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_report(display: pd.DataFrame) -> str:
    pitching = "IP" in display.columns
    kind = "Pitching" if pitching else "Batting"
    stat_order = PITCHING_COLUMNS if pitching else BATTING_COLUMNS
    columns = [*IDENTITY_COLUMNS, *[c for c in stat_order if c in display]]
    columns += [c for c in display.columns if c not in columns]
    frame = display.reindex(columns=columns, fill_value="")
    years = ", ".join(sorted({_cell(v) for v in frame["Year"] if _cell(v)})) or "—"
    title = f"{kind} projections"
    count = len(frame)
    notes = (
        "IP uses baseball notation: .1 is one out; .2 is two outs. ERA and per-nine rates use true innings before rounding. WHIP uses three decimals."
        if pitching
        else "BA, OBP, SLG, and OPS use three decimal places. Counting statistics are rounded to whole numbers."
    )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backcaster · {title} · {escape(years)}</title><style>{REPORT_CSS}</style></head>
<body><header class="topbar"><div class="brand"><span class="brand-mark" aria-hidden="true"></span>Backcaster</div><small>PLAYER PROJECTION REPORT</small></header>
<main><section class="intro"><p class="eyebrow">Season outlook</p><h1>{title}</h1><p class="subtitle">A clear view of projected player performance.</p></section>
<section class="cards" aria-label="Report summary"><div class="card"><div class="card-label">Players in report</div><div class="card-value">{count:,}</div><div class="card-note">One row per projected player</div></div>
<div class="card"><div class="card-label">Projection year</div><div class="card-value">{escape(years)}</div><div class="card-note">The season being projected</div></div>
<div class="card"><div class="card-label">Projection type</div><div class="card-value">{kind}</div><div class="card-note">Marcel-style statistical baseline</div></div></section>
<section class="panel" aria-label="Player projections"><div class="toolbar"><div><h2>Player projections</h2><p class="table-hint">Select a column heading to sort.</p></div>
<div class="controls"><label for="search">Find players</label><input id="search" type="search" placeholder="Search name, ID, or statistic…" autocomplete="off"><button type="button" class="action" id="reset">Reset</button><button type="button" class="action primary" id="print">Print report</button></div></div>
<div class="table-scroll" tabindex="0" aria-label="Scrollable projection statistics">{_table(frame, columns)}</div>
<p class="empty" id="no-matches"{"" if count == 0 else " hidden"}>No players to display.</p>
<div class="table-footer"><span id="visible-count" role="status" aria-live="polite">Showing {count} of {count} players</span><span>Rounded for presentation</span></div></section>
<section class="report-notes" aria-label="Reading this report"><div><strong>Reading the numbers</strong>{notes}</div><div><strong>Interpreting projections</strong>Reliability is an observed-evidence weight, not an accuracy probability. Historical eligibility does not represent a current roster.</div></section>
<footer><span>Backcaster · Marcel-style projections</span><span>Methodology: Tom Tango · Reference inspiration: Ben Dilday’s marcelR</span></footer></main>
<script>{REPORT_JS}</script></body></html>'''
