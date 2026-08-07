import json
import re
import argparse
from datetime import datetime
from urllib.parse import urlencode, quote
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.amazon.jobs/en/search"
BASE_PARAMS = {
    "result_limit": "10",
    "sort": "recent",
    "distanceType": "Mi",
    "radius": "24km",
    "loc_group_id": "seattle-metro",
    "loc_query": "Greater Seattle Area, WA, United States",
}

def build_url(query, offset=0, sort="recent"):
    params = {**BASE_PARAMS, "sort": sort, "base_query": query, "offset": str(offset)}
    return f"{BASE_URL}?{urlencode(params, quote_via=quote)}"

def parse_posted_date(text):
    """Convert 'Posted May 21, 2026' to days ago as a float."""
    m = re.search(r"Posted\s+(\w+ \d+,\s*\d{4})", text.strip())
    if not m:
        return None
    dt = datetime.strptime(m.group(1), "%B %d, %Y")
    return (datetime.now() - dt).days

def scrape_amazon(query, sort="recent", max_pages=5):
    result_limit = 10
    jobs = []
    first_url = build_url(query, offset=0, sort=sort)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False)
        page = browser.new_page()

        for page_num in range(max_pages):
            offset = page_num * result_limit
            url = build_url(query, offset, sort=sort)
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            cards = page.locator("div.job-tile-lists div.job-tile").all()
            if not cards:
                break

            for card in cards:
                try:
                    job_div   = card.locator("div.job")
                    job_id    = job_div.get_attribute("data-job-id")
                    link      = card.locator("a.job-link")
                    title     = link.inner_text().strip()
                    href      = link.get_attribute("href")
                    posted_text = card.locator("span.posting-date").inner_text().strip()
                    interval_days = parse_posted_date(posted_text)
                    loc_el    = card.locator("li.text-nowrap")
                    location  = loc_el.first.inner_text().strip() if loc_el.count() > 0 else None

                    jobs.append({
                        "job_id": job_id,
                        "title": title,
                        "posted": posted_text,
                        "interval_days": interval_days,
                        "location": location,
                        "href": f"https://www.amazon.jobs{href}" if href else None,
                    })
                except Exception:
                    pass

        browser.close()

    seen = set()
    deduped = []
    for job in jobs:
        if job["job_id"] not in seen:
            seen.add(job["job_id"])
            deduped.append(job)

    output = {
        "metadata": {
            "source": "amazon",
            "url": first_url,
            "params": {"query": query, "sort": sort, "max_pages": max_pages},
            "scraped_at": datetime.now().isoformat(),
        },
        "results": deduped,
    }
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Job Scanner")
    parser.add_argument("--base_query", type=str, default="data science")
    parser.add_argument("--sort", type=str, default="recent", choices=["recent", "relevant"])
    parser.add_argument("--max_pages", type=int, default=5)
    args = parser.parse_args()

    output = scrape_amazon(query=args.base_query, sort=args.sort, max_pages=args.max_pages)

    with open("amazon_jobs.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {len(output['results'])} jobs to amazon_jobs.json")
