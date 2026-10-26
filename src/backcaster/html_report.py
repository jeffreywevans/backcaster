"""Self-contained HTML projection reports, with no network assets."""

from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd

from backcaster.stat_columns import BATTING_STAT_COLUMNS, IDENTITY_COLUMNS, PITCHING_STAT_COLUMNS

BATTING_COLUMNS = (*BATTING_STAT_COLUMNS, "Reliability", "ConfidenceTier")
PITCHING_COLUMNS = (*PITCHING_STAT_COLUMNS, "Reliability", "ConfidenceTier")
TABLE_ROW_END = "</tr>"
COLUMN_LABELS = {
    "PlayerID": "Player ID",
    "ConfidenceTier": "Confidence tier",
    "EligibilityAsOf": "Eligibility as of",
}
COLUMN_HELP = {
    "IP": "Innings in baseball notation: .1 = one out, .2 = two outs",
    "Reliability": "Observed-evidence weight; not a probability of prediction accuracy",
    "ConfidenceTier": "core: reliability at least 0.50; low-sample: below 0.50. Both receive projections.",
    "Age": "Projection year minus birth year",
}

REPORT_CSS = r"""
:root { --brand:#153e3b; --brand-dark:#102e2c; --accent:#78bd82; --positive:#14733b; --positive-bg:#e9f7ee; --negative:#b4232f; --negative-bg:#fff0f1; --canvas:#f3f6f5; --surface:#fff; --ink:#183634; --muted:#617571; --line:#dce5e2; --stripe:#f8faf9; --radius:12px; }
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
th,td { padding:11px 13px; white-space:nowrap; text-align:center; border-bottom:1px solid #eaf0ed; }
th { position:sticky; top:0; background:#eaf0ed; color:#49605b; z-index:2; font-size:11px; letter-spacing:.02em; }
th button { position:relative; background:none; color:inherit; border:0; padding:0; font-weight:700; white-space:nowrap; }
th button::after { position:absolute; left:100%; top:0; margin-left:4px; content:' ↕'; opacity:.4; font-weight:400; }
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
.compare-toggle { border:0; background:transparent; color:inherit; font:inherit; font-weight:600; padding:0; display:inline-flex; align-items:center; gap:7px; }
.compare-toggle .chevron { color:var(--brand); width:10px; transition:transform .15s ease; }
.compare-toggle[aria-expanded=false] .chevron { transform:rotate(-90deg); }
.detail-row { background:var(--stripe); color:#49605b; }
.detail-row td { padding-top:8px; padding-bottom:8px; }
.detail-row td:first-child { padding-left:30px; font-weight:650; color:var(--muted); }
.variance-row { border-bottom:2px solid var(--line); }
.rate { color:var(--brand); font-weight:650; background-color:#78bd8209; }
.variance-positive { color:var(--positive); background:var(--positive-bg); font-weight:700; }
.variance-negative { color:var(--negative); background:var(--negative-bg); font-weight:700; }
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
 const players=Array.from(body.querySelectorAll('tr[data-player]'));
 const groups=players.map(player=>({
   player,
   details:Array.from(body.querySelectorAll(`tr[data-detail][data-group="${player.dataset.group}"]`))
 }));
 const search=document.getElementById('search');
 const status=document.getElementById('visible-count');
 const empty=document.getElementById('no-matches');
 let active=-1, ascending=true;
 function append(group) { body.appendChild(group.player); group.details.forEach(row=>body.appendChild(row)); }
 function filter() {
   const query=search.value.trim().toLocaleLowerCase();
   let visible=0;
   groups.forEach(group=>{
     const matches=[group.player,...group.details].some(row=>row.textContent.toLocaleLowerCase().includes(query));
     group.player.hidden=!matches;
     group.details.forEach(row=>{row.hidden=!matches||group.player.dataset.expanded==='false';});
     if(matches)visible++;
   });
   status.textContent=`Showing ${visible} of ${groups.length} players`;
   empty.hidden=visible!==0;
 }
 table.querySelectorAll('thead button').forEach((button,index)=>{
   button.addEventListener('click',()=>{
     ascending=active===index?!ascending:true; active=index;
     const sorted=[...groups].sort((a,b)=>{
       const x=a.player.cells[index].textContent.trim(), y=b.player.cells[index].textContent.trim();
       const numeric=x!==''&&y!==''&&Number.isFinite(Number(x))&&Number.isFinite(Number(y));
       return (numeric?Number(x)-Number(y):x.localeCompare(y,undefined,{numeric:true}))*(ascending?1:-1);
     });
     table.querySelectorAll('th').forEach(th=>th.setAttribute('aria-sort','none'));
     button.parentElement.setAttribute('aria-sort',ascending?'ascending':'descending');
     sorted.forEach(append); filter();
   });
 });
 function setExpanded(player,expanded) {
   const button=player.querySelector('.compare-toggle');
   if(!button)return;
   button.setAttribute('aria-expanded',String(expanded));
   button.setAttribute('aria-label',`${expanded?'Hide':'Show'} historical comparison for ${button.dataset.name}`);
   player.dataset.expanded=String(expanded);
 }
 function setAllExpanded(expanded) {
   groups.forEach(group=>setExpanded(group.player,expanded));
   filter();
 }
 body.querySelectorAll('.compare-toggle').forEach(button=>button.addEventListener('click',()=>{
   setExpanded(button.closest('tr'),button.getAttribute('aria-expanded')!=='true');
   filter();
 }));
 document.getElementById('expand-all')?.addEventListener('click',()=>setAllExpanded(true));
 document.getElementById('collapse-all')?.addEventListener('click',()=>setAllExpanded(false));
 search.addEventListener('input',filter);
 document.getElementById('reset').addEventListener('click',()=>{
   search.value='';active=-1;ascending=true;
   groups.forEach(group=>{
     setExpanded(group.player,false);
     append(group);
   });
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


RATE_COLUMNS = {
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


def _row_cells(
    values: dict[str, Any], columns: list[str], row_type: str, group: int, comparison: bool
) -> str:
    cells = []
    for column in columns:
        value = _cell(values.get(column, ""))
        classes = ["rate"] if column in RATE_COLUMNS else []
        if row_type == "variance" and value.startswith("+"):
            classes.append("variance-positive")
        elif row_type == "variance" and value.startswith("-"):
            classes.append("variance-negative")
        class_attribute = f' class="{" ".join(classes)}"' if classes else ""
        content = escape(value)
        if column == "Name" and row_type == "projection" and comparison:
            player_name = escape(value, quote=True)
            content = (
                f'<button type="button" class="compare-toggle" aria-expanded="false" '
                f'aria-controls="actual-{group} variance-{group}" '
                f'aria-label="Show historical comparison for {player_name}" '
                f'data-name="{player_name}"><span class="chevron" aria-hidden="true">▾</span>'
                f"<span>{escape(value)}</span></button>"
            )
        cells.append(f"<td{class_attribute}>{content}</td>")
    return "".join(cells)


def _comparison_values(
    player_id: str,
    columns: list[str],
    indexed: pd.DataFrame,
    label: str,
    missing_label: str,
) -> dict[str, Any]:
    values: dict[str, Any] = dict.fromkeys(columns, "")
    if player_id not in indexed.index:
        values["Name"] = missing_label
        return values
    values.update({str(key): value for key, value in indexed.loc[player_id].items()})
    values["Name"] = label
    for column in IDENTITY_COLUMNS[1:]:
        values[column] = ""
    return values


def _table(
    frame: pd.DataFrame,
    columns: list[str],
    actuals: pd.DataFrame | None = None,
    variances: pd.DataFrame | None = None,
) -> str:
    headers = []
    for column in columns:
        label = escape(COLUMN_LABELS.get(column, column))
        title = escape(
            COLUMN_HELP.get(column, f"Sort by {COLUMN_LABELS.get(column, column)}"), quote=True
        )
        headers.append(
            f'<th scope="col" aria-sort="none"><button type="button" title="{title}">{label}</button></th>'
        )
    comparison = actuals is not None and variances is not None
    actual_by_id = actuals.set_index("PlayerID") if actuals is not None else pd.DataFrame()
    variance_by_id = variances.set_index("PlayerID") if variances is not None else pd.DataFrame()
    rows = []
    for group, record in enumerate(frame.to_dict(orient="records")):
        values = {str(key): value for key, value in record.items()}
        rows.append(
            f'<tr data-player="true" data-group="{group}" data-expanded="false">'
            + _row_cells(values, columns, "projection", group, comparison)
            + TABLE_ROW_END
        )
        if comparison:
            player_id = _cell(values.get("PlayerID", ""))
            actual_values = _comparison_values(
                player_id, columns, actual_by_id, "Actual", "Actual (no recorded stats)"
            )
            variance_values = _comparison_values(
                player_id, columns, variance_by_id, "Variance", "Variance"
            )
            rows.append(
                f'<tr class="detail-row actual-row" data-detail="true" data-group="{group}" '
                f'id="actual-{group}" hidden>'
                + _row_cells(actual_values, columns, "actual", group, comparison)
                + TABLE_ROW_END
            )
            rows.append(
                f'<tr class="detail-row variance-row" data-detail="true" data-group="{group}" '
                f'id="variance-{group}" hidden>'
                + _row_cells(variance_values, columns, "variance", group, comparison)
                + TABLE_ROW_END
            )
    return (
        '<table id="projections"><caption class="sr-only">Player projection statistics</caption><thead><tr>'
        + "".join(headers)
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_report(
    display: pd.DataFrame,
    actuals: pd.DataFrame | None = None,
    variances: pd.DataFrame | None = None,
) -> str:
    pitching = "IP" in display.columns
    kind = "Pitching" if pitching else "Batting"
    stat_order = PITCHING_COLUMNS if pitching else BATTING_COLUMNS
    columns = [*IDENTITY_COLUMNS, *[c for c in stat_order if c in display]]
    columns += [c for c in display.columns if c not in columns]
    frame = display.reindex(columns=columns, fill_value="")
    actual_frame = actuals.reindex(columns=columns, fill_value="") if actuals is not None else None
    variance_frame = (
        variances.reindex(columns=columns, fill_value="") if variances is not None else None
    )
    comparison = actual_frame is not None and variance_frame is not None
    years = ", ".join(sorted({_cell(v) for v in frame["Year"] if _cell(v)})) or "—"
    title = f"{kind} projections"
    count = len(frame)
    notes = (
        "IP uses baseball notation: .1 is one out; .2 is two outs. ERA and per-nine rates use true innings before rounding. WHIP uses three decimals."
        if pitching
        else "BA, OBP, SLG, and OPS use three decimal places. Counting statistics are rounded to whole numbers."
    )
    comparison_note = (
        " Variance is actual minus projected; positive values are green and negative values are red."
        if comparison
        else ""
    )
    row_note = (
        "Projection, actual, and variance rows" if comparison else "One row per projected player"
    )
    table_hint = (
        "Comparisons start collapsed. Expand a player, expand all, or collapse all. Select a column heading to sort."
        if comparison
        else "Select a column heading to sort."
    )
    comparison_controls = (
        '<button type="button" class="action" id="expand-all" aria-controls="projections">Expand all</button>'
        '<button type="button" class="action" id="collapse-all" aria-controls="projections">Collapse all</button>'
        if comparison
        else ""
    )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backcaster · {title} · {escape(years)}</title><style>{REPORT_CSS}</style></head>
<body><header class="topbar"><div class="brand"><span class="brand-mark" aria-hidden="true"></span>Backcaster</div><small>PLAYER PROJECTION REPORT</small></header>
<main><section class="intro"><p class="eyebrow">Season outlook</p><h1>{title}</h1><p class="subtitle">A clear view of projected player performance.</p></section>
<section class="cards" aria-label="Report summary"><div class="card"><div class="card-label">Players in report</div><div class="card-value">{count:,}</div><div class="card-note">{row_note}</div></div>
<div class="card"><div class="card-label">Projection year</div><div class="card-value">{escape(years)}</div><div class="card-note">The season being projected</div></div>
<div class="card"><div class="card-label">Projection type</div><div class="card-value">{kind}</div><div class="card-note">Marcel-style statistical baseline</div></div></section>
<section class="panel" aria-label="Player projections"><div class="toolbar"><div><h2>Player projections</h2><p class="table-hint">{table_hint}</p></div>
<div class="controls"><label for="search">Find players</label><input id="search" type="search" placeholder="Search name, ID, or statistic…" autocomplete="off">{comparison_controls}<button type="button" class="action" id="reset">Reset</button><button type="button" class="action primary" id="print">Print report</button></div></div>
<div class="table-scroll" tabindex="0" aria-label="Scrollable projection statistics">{_table(frame, columns, actual_frame, variance_frame)}</div>
<p class="empty" id="no-matches"{"" if count == 0 else " hidden"}>No players to display.</p>
<div class="table-footer"><span id="visible-count" role="status" aria-live="polite">Showing {count} of {count} players</span><span>Rounded for presentation</span></div></section>
<section class="report-notes" aria-label="Reading this report"><div><strong>Reading the numbers</strong>{notes}{comparison_note}</div><div><strong>Interpreting projections</strong>Reliability is an observed-evidence weight, not an accuracy probability. Historical eligibility does not represent a current roster.</div></section>
<footer><span>Backcaster · Marcel-style projections</span><span>Methodology: Tom Tango · Reference inspiration: Ben Dilday’s marcelR</span></footer></main>
<script>{REPORT_JS}</script></body></html>'''
