import json
import os
import pandas as pd
from datetime import datetime
from openpyxl.styles import Font
from relevance import filter_relevant
from scraper_core import scrape_site
from sites import SITES

RESULT_COLS = ["job_id", "title", "posted", "interval_days", "location", "href"]

outputDir = 'output'


def scan(site_key, queries, max_pages=5):
    """Run one or more searches against a configured site, deduplicate, and save
    the full result set to <site_key>_jobs_<date>.json.

    site_key must be a key in sites.SITES (e.g. "amazon", "microsoft").
    Returns (df, json_path) -- df holds every job found, unfiltered.
    """
    if isinstance(queries, str):
        queries = [queries]
    config = SITES[site_key]

    all_results = []
    for q in queries:
        all_results.extend(scrape_site(config, q, max_pages=max_pages)["results"])

    deduped = _dedup(all_results)
    json_out = _json_name(site_key)

    with open(json_out, "w", encoding="utf-8") as f:
        json.dump({"metadata": {"source": site_key, "queries": queries, "scraped_at": datetime.now().isoformat()}, "results": deduped}, f, indent=2)

    df = pd.DataFrame(deduped, columns=RESULT_COLS)
    print(f"Saved {len(df)} {site_key} jobs → {json_out}")
    return df, json_out


def export_excel(df, tab, excel_out=None, max_interval=100, keywords=None):
    """Filter a scanned df down to relevant, recent jobs and write it to an Excel tab.

    - max_interval: drop jobs posted more than this many days ago. Jobs whose
      site exposes no posting date (interval_days is null) are always kept,
      since there's nothing to filter them on.
    - keywords: override the default title-relevance keyword list (see relevance.py).
    """
    filtered = df[df["interval_days"].isna() | (df["interval_days"] <= max_interval)]
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
