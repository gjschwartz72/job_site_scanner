import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import csv
import re
from playwright.sync_api import sync_playwright

URL = "https://apply.careers.microsoft.com/careers?query=Data+Science&start=0&location=United+States%2C+Washington%2C+Redmond&pid=1970393556823722&sort_by=relevance&filter_distance=160&filter_include_remote=1"

def clean(text):
    return re.sub(r"\s+", " ", text).strip()

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=False)
    page = browser.new_page()
    page.goto(URL, wait_until="domcontentloaded")

    # let the job list render
    page.wait_for_timeout(5000)

    # Grab all links on the page
    links = page.locator("a").all()

    jobs = []

    for link in links:
        try:
            text = clean(link.inner_text())
            href = link.get_attribute("href")

            # Heuristic: keep only links that look like job cards
            if not text:
                continue
            if "Posted " not in text:
                continue

            lines = [x.strip() for x in text.split("\n") if x.strip()]

            title = None
            posted = None
            location = None

            # Example card text often looks like:
            # Senior Applied Scientist- Microsoft Excel team
            # United States, Washington, Redmond
            # Posted 2 hours ago
            if len(lines) >= 1:
                title = lines[0]

            for line in lines[1:]:
                if line.startswith("Posted "):
                    posted = line
                elif "United States" in line or "," in line:
                    location = line

            jobs.append({
                "title": title,
                "posted": posted,
                "location": location,
                "href": href
            })

        except Exception:
            pass

    # dedupe
    seen = set()
    deduped = []
    for job in jobs:
        key = (job["title"], job["posted"], job["location"], job["href"])
        if key not in seen:
            seen.add(key)
            deduped.append(job)

    for job in deduped[:20]:
        print(job)

    browser.close()