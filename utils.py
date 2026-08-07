import re
import json
import os
import subprocess
import pandas as pd
from datetime import datetime
from openpyxl.styles import Font
from relevance import filter_relevant

RESULT_COLS = ["job_id", "title", "posted", "interval_days", "location", "href"]

outputDir = 'output'
def scan_ms(queries, max_pages=5, sort_by="relevant"):
    """Run one or more MS searches, deduplicate, and save the full result set to ms_jobs.json.

    Returns (df, json_path) -- df holds every job found, unfiltered.
    """
    if isinstance(queries, str):
        queries = [queries]

    all_results = []
    for q in queries:
        all_results.extend(_run_query("search_ms.py", ["--query", q, "--max_pages", str(max_pages), "--sortBy", sort_by], "ms_jobs.json"))

    deduped = _dedup(all_results)
    json_out = _json_name("ms")

    with open(json_out, "w", encoding="utf-8") as f:
        json.dump({"metadata": {"source": "microsoft", "queries": queries, "scraped_at": datetime.now().isoformat()}, "results": deduped}, f, indent=2)

    df = pd.DataFrame(deduped, columns=RESULT_COLS)
    print(f"Saved {len(df)} Microsoft jobs → {json_out}")
    return df, json_out


def scan_amazon(queries, max_pages=5, sort_by="recent"):
    """Run one or more Amazon searches, deduplicate, and save the full result set to amazon_jobs.json.

    Returns (df, json_path) -- df holds every job found, unfiltered.
    """
    if isinstance(queries, str):
        queries = [queries]

    all_results = []
    for q in queries:
        all_results.extend(_run_query("search_amazon.py", ["--base_query", q, "--max_pages", str(max_pages), "--sort", sort_by], "amazon_jobs.json"))

    deduped = _dedup(all_results)
    json_out = _json_name("amazon")

    with open(json_out, "w", encoding="utf-8") as f:
        json.dump({"metadata": {"source": "amazon", "queries": queries, "scraped_at": datetime.now().isoformat()}, "results": deduped}, f, indent=2)

    df = pd.DataFrame(deduped, columns=RESULT_COLS)
    print(f"Saved {len(df)} Amazon jobs → {json_out}")
    return df, json_out


def export_excel(df, tab, excel_out=None, max_interval=100, keywords=None):
    """Filter a scanned df down to relevant, recent jobs and write it to an Excel tab.

    - max_interval: drop jobs posted more than this many days ago.
    - keywords: override the default title-relevance keyword list (see relevance.py).
    """
    filtered = df.query(f"interval_days <= {max_interval}")
    filtered = filter_relevant(filtered, keywords)
    filtered = filtered.sort_values("interval_days")

    excel = _excel_name(excel_out)
    _write_sheet(filtered, excel, tab)
    print(f"Wrote {len(filtered)}/{len(df)} relevant jobs → {excel} (sheet '{tab}')")
    return filtered


# ── private helpers ────────────────────────────────────────────────────────────

def _excel_name(excel_out):
    if excel_out:
        return excel_out
    dt = datetime.now()
    return f'jobs_{dt.year}_{dt.month:02d}_{dt.day:02d}.xlsx'


def _json_name(source):
    dt = datetime.now()
    return f'{source}_jobs_{dt.year}_{dt.month:02d}_{dt.day:02d}.json'


def _run_query(script, args, json_file):
    """Run a scraper subprocess and return its results list."""
    subprocess.run(["python", script] + args, check=True)
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)["results"]


def _dedup(results):
    """Deduplicate by job_id, preserving order."""
    seen = set()
    out = []
    for r in results:
        jid = r.get("job_id")
        if jid not in seen:
            seen.add(jid)
            out.append(r)
    return out


def _write_sheet(df, fName, tab):
    """Write df to a named sheet, creating the workbook if it doesn't exist."""
    mode = "a" if os.path.exists(fName) else "w"
    kwargs = {"if_sheet_exists": "replace"} if mode == "a" else {}
    with pd.ExcelWriter(outputDir + "/" + fName, engine="openpyxl", mode=mode, **kwargs) as writer:
        df.to_excel(writer, sheet_name=tab, index=False)
        _apply_hyperlinks(writer.sheets[tab], df)


def _apply_hyperlinks(ws, df):
    """Set live hyperlinks on the href column of an openpyxl worksheet."""
    if "href" not in df.columns:
        return
    col_idx = df.columns.get_loc("href") + 1
    link_font = Font(color="0563C1", underline="single")
    for row_offset, (_, row) in enumerate(df.iterrows()):
        url = row["href"]
        if pd.isna(url) or not url:
            continue
        cell = ws.cell(row=row_offset + 2, column=col_idx)
        cell.hyperlink = url
        cell.font = link_font


def interval_to_hours(text, asDays=True):
    text = text.strip().lower()
    pattern = r"(an?\b|\d+)\s+(minute|hour|day|month|year)s?\s+ago"
    m = re.match(pattern, text)
    if not m:
        raise ValueError(f"Cannot parse interval: {text}")
    value, unit = m.groups()
    value = 1 if value in ("a", "an") else int(value)
    hours_per_unit = {"minute": 1/60, "hour": 1, "day": 24, "month": 24*30, "year": 24*365}
    hours = value * hours_per_unit[unit]
    return hours / 24 if asDays else hours
