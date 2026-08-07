"""Generic Playwright scraping engine, driven by a SiteConfig (see site_config.py).

Every site funnels through scrape_site(), which normalizes output to:
    {"metadata": {...}, "results": [{"job_id", "title", "posted", "interval_days", "location", "href"}, ...]}
"""
import argparse
import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

from site_config import OffsetPagination, ClickPagination
from sites import SITES


def scrape_site(config, query, max_pages=5):
    first_url = config.build_url(query, offset=0)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False)
        page = browser.new_page()

        if config.custom_extractor:
            raw_jobs = config.custom_extractor(page, config, query, max_pages)
        elif isinstance(config.pagination, OffsetPagination):
            raw_jobs = _scrape_offset(page, config, query, max_pages)
        elif isinstance(config.pagination, ClickPagination):
            raw_jobs = _scrape_click(page, config, query, max_pages)
        else:
            raise ValueError(f"Unsupported pagination type: {config.pagination}")

        browser.close()

    for job in raw_jobs:
        job["interval_days"] = _parse_interval_days(job.get("posted"), config.date_format)

    return {
        "metadata": {
            "source": config.name,
            "url": first_url,
            "params": {"query": query, "max_pages": max_pages},
            "scraped_at": datetime.now().isoformat(),
        },
        "results": _dedup(raw_jobs),
    }


# ── pagination strategies ───────────────────────────────────────────────────

def _scrape_offset(page, config, query, max_pages):
    jobs = []
    page_size = config.pagination.page_size
    for page_num in range(max_pages):
        offset = page_num * page_size
        page.goto(config.build_url(query, offset), wait_until="domcontentloaded")
        page.wait_for_timeout(config.goto_wait_ms)

        cards = page.locator(config.selectors.card).all()
        if not cards:
            break
        for card in cards:
            job = _extract_card(card, config)
            if job:
                jobs.append(job)
    return jobs


def _scrape_click(page, config, query, max_pages):
    jobs = []
    page.goto(config.build_url(query), wait_until="domcontentloaded")
    page.wait_for_timeout(config.goto_wait_ms)

    page_count = 0
    while page_count < max_pages:
        cards = page.locator(config.selectors.card).all()
        for card in cards:
            job = _extract_card(card, config)
            if job:
                jobs.append(job)

        next_btn = page.locator(config.pagination.next_button_selector)
        if next_btn.count() == 0 or next_btn.get_attribute(config.pagination.disabled_attr) == "true":
            break
        next_btn.click()
        page_count += 1
        page.wait_for_timeout(config.pagination.wait_ms)
    return jobs


def _extract_card(card, config):
    sel = config.selectors
    try:
        link_el = card.locator(sel.link)
        href = link_el.get_attribute("href")
        title = (card.locator(sel.title).inner_text() if sel.title else link_el.inner_text()).strip()

        posted = card.locator(sel.date).inner_text().strip() if sel.date else None

        location = None
        if sel.location:
            loc_el = card.locator(sel.location)
            location = loc_el.first.inner_text().strip() if loc_el.count() > 0 else None

        if sel.job_id_attr:
            id_sel, attr = sel.job_id_attr
            job_id = card.locator(id_sel).get_attribute(attr)
        else:
            job_id = href.rstrip("/").split("/")[-1] if href else None

        full_href = f"{config.href_prefix}{href}" if href and href.startswith("/") else href

        return {"job_id": job_id, "title": title, "posted": posted, "location": location, "href": full_href}
    except Exception:
        return None


# ── date normalization ──────────────────────────────────────────────────────

_RELATIVE_RE = re.compile(r"(an?\b|\d+)\s+(minute|hour|day|month|year)s?\s+ago")
_HOURS_PER_UNIT = {"minute": 1 / 60, "hour": 1, "day": 24, "month": 24 * 30, "year": 24 * 365}


def _parse_interval_days(posted_text, date_format):
    if not posted_text:
        return None

    if date_format == "relative":
        m = _RELATIVE_RE.search(posted_text.strip().lower())
        if not m:
            return None
        value, unit = m.groups()
        value = 1 if value in ("a", "an") else int(value)
        return (value * _HOURS_PER_UNIT[unit]) / 24

    if date_format.startswith("absolute:"):
        fmt = date_format[len("absolute:"):]
        m = re.search(r"Posted\s+(.+)", posted_text.strip())
        if not m:
            return None
        dt = datetime.strptime(m.group(1).strip(), fmt)
        return (datetime.now() - dt).days

    raise ValueError(f"Unknown date_format: {date_format}")


def _dedup(jobs):
    seen = set()
    out = []
    for job in jobs:
        key = job.get("job_id") or (job.get("title"), job.get("location"), job.get("href"))
        if key not in seen:
            seen.add(key)
            out.append(job)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generic job site scraper")
    parser.add_argument("--site", required=True, choices=list(SITES.keys()))
    parser.add_argument("--query", type=str, default="data science")
    parser.add_argument("--max_pages", type=int, default=5)
    args = parser.parse_args()

    output = scrape_site(SITES[args.site], query=args.query, max_pages=args.max_pages)

    out_file = f"{args.site}_jobs.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {len(output['results'])} jobs to {out_file}")
