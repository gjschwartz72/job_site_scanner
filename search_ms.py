# scrape_ms_jobs.py
import json
import re
import argparse
from datetime import datetime
from urllib.parse import urljoin, quote_plus
from playwright.sync_api import sync_playwright
from utils import interval_to_hours

BASE_URL = "https://apply.careers.microsoft.com/careers"
BASE_SUFFIX = "&start=0&location=United+States%2C+Washington%2C+Redmond&pid=1970393556823722&sort_by=relevance&filter_distance=160&filter_include_remote=1"

def build_url(query_arg):
    return f"{BASE_URL}?query={quote_plus(query_arg)}{BASE_SUFFIX}"

def clean(text):
    return re.sub(r"\s+", " ", text).strip()

def scrape_microsoft(url, query="", max_pages=5, sortBy="relevant"):
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        if sortBy == 'latest':
            page.locator('[aria-label^="Sort by"]').click()
            page.wait_for_selector('input[name="sort_options"]')
            page.locator('input[name="sort_options"][value="timestamp"]').click()
            page.wait_for_timeout(5000)

        links = page.locator("a").all()
        jobs = []
        page_count = 0
        while page_count < max_pages:

            links = page.locator("a").all()

            for link in links:
                try:
                    text = clean(link.inner_text())
                    href = link.get_attribute("href")

                    if not text or "Posted " not in text:
                        continue

                    lines = [x.strip() for x in text.split("\n") if x.strip()]
                    title = lines[0].split(' Posted ')[0] if lines else None
                    posted = lines[0].split(' Posted ')[1] if lines else None

                    if posted.startswith("a "):
                        posted = posted.replace("a ", "1 ")

                    location = None

                    for line in lines[1:]:
                        if line.startswith("Posted "):
                            posted = line
                        elif "United States" in line or "," in line:
                            location = line

                    if href:
                        href = urljoin(page.url, href)
                        job_id = href.split("/")[-1]

                    jobs.append({
                        "job_id": job_id,
                        "title": title,
                        "posted": posted,
                        "interval_days": interval_to_hours(posted),
                        "location": location,
                        "href": href,
                    })

                except Exception:
                    pass

            # ---- pagination ----
            next_btn = page.locator('button[aria-label="Next jobs"]')

            if next_btn.get_attribute("aria-disabled") == "true":
                break

            next_btn.click()

            page_count += 1
            # wait for new jobs to load
            page.wait_for_timeout(1000)

# ------------------
        browser.close()

        seen = set()
        deduped = []
        for job in jobs:
            key = (job["title"], job["posted"], job["location"], job["href"])
            if key not in seen:
                seen.add(key)
                deduped.append(job)

    output = {
        "metadata": {
            "source": "microsoft",
            "url": url,
            "params": {"query": query, "sort": sortBy, "max_pages": max_pages},
            "scraped_at": datetime.now().isoformat(),
        },
        "results": deduped,
    }
    return output

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Microsoft Job Scanner")

    parser.add_argument(
        "--query",
        type=str,
        default="data science",
        help="Search query string, URL-encoded and appended to the Microsoft Careers search URL.",
    )

    parser.add_argument(
        "--max_pages",
        type=int,
        default=5,
        help="Number of pages to scrape"
    )

    parser.add_argument(
        "--sortBy",
        type=str,
        default="relevant",
        choices=["relevant", "latest"],
        help="Sort order for jobs"
    )

    args = parser.parse_args()

    url = build_url(args.query)
    print(f"Scraping: {url}")

    output = scrape_microsoft(
        url=url,
        query=args.query,
        max_pages=args.max_pages,
        sortBy=args.sortBy,
    )

    with open("ms_jobs.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {len(output['results'])} jobs to ms_jobs.json")