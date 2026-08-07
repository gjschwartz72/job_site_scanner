"""Per-site configuration registry.

Most new sites (Greenhouse, Lever, Workday, iCIMS, and similar ATS platforms)
just need a SiteConfig entry with a URL pattern and a handful of CSS selectors --
see amazon below for the template. Sites whose listings aren't clean repeating
cards (see microsoft below) need a small custom_extractor function instead.
"""
import re
from urllib.parse import quote_plus, urljoin

from site_config import SiteConfig, OffsetPagination, PagePagination, ClickPagination, CardSelectors, is_disabled


# ── Amazon: card-based, offset pagination, absolute "Posted <date>" text ───

AMAZON = SiteConfig(
    name="amazon",
    base_url="https://www.amazon.jobs/en/search",
    query_param="base_query",
    static_params={
        "result_limit": "10",
        "sort": "recent",
        "distanceType": "Mi",
        "radius": "24km",
        "loc_group_id": "seattle-metro",
        "loc_query": "Greater Seattle Area, WA, United States",
    },
    pagination=OffsetPagination(param="offset", page_size=10),
    date_format="absolute:%B %d, %Y",
    href_prefix="https://www.amazon.jobs",
    selectors=CardSelectors(
        card="div.job-tile-lists div.job-tile",
        link="a.job-link",
        date="span.posting-date",
        location="li.text-nowrap",
        job_id_attr=("div.job", "data-job-id"),
    ),
)


# ── Microsoft: not card-based (job rows are bare <a> tags), so it needs a
#    custom extractor. Pagination is still declarative (click "Next jobs"). ──

def _clean(text):
    return re.sub(r"\s+", " ", text).strip()


def _extract_microsoft(page, config, query, max_pages):
    page.goto(config.build_url(query), wait_until="domcontentloaded")
    page.wait_for_timeout(config.goto_wait_ms)

    jobs = []
    page_count = 0
    while page_count < max_pages:
        for link in page.locator("a").all():
            try:
                text = _clean(link.inner_text())
                if not text or "Posted " not in text:
                    continue

                lines = [x.strip() for x in text.split("\n") if x.strip()]
                title = lines[0].split(" Posted ")[0]
                posted = lines[0].split(" Posted ")[1] if " Posted " in lines[0] else None
                location = None

                for line in lines[1:]:
                    if line.startswith("Posted "):
                        posted = line
                    elif "United States" in line or "," in line:
                        location = line

                href = link.get_attribute("href")
                if href:
                    href = urljoin(page.url, href)
                job_id = href.rstrip("/").split("/")[-1] if href else None

                jobs.append({"job_id": job_id, "title": title, "posted": posted, "location": location, "href": href})
            except Exception:
                pass

        next_btn = page.locator(config.pagination.next_button_selector)
        if is_disabled(next_btn, config.pagination.disabled_attr):
            break
        next_btn.click()
        page_count += 1
        page.wait_for_timeout(config.pagination.wait_ms)

    return jobs


MICROSOFT = SiteConfig(
    name="microsoft",
    base_url="https://apply.careers.microsoft.com/careers",
    query_param="query",
    static_params={
        "start": "0",
        "location": "United States, Washington, Redmond",
        "pid": "1970393556823722",
        "sort_by": "relevance",
        "filter_distance": "160",
        "filter_include_remote": "1",
    },
    pagination=ClickPagination(next_button_selector='button[aria-label="Next jobs"]'),
    date_format="relative",
    quote_via=quote_plus,
    custom_extractor=_extract_microsoft,
    goto_wait_ms=5000,
)


# ── Stripe: card-based, page-number pagination, no posting date exposed ────
# (Neither the search results nor an individual listing page show a posted/
# updated date anywhere, so date_format is left unset -- interval_days will
# always be null for Stripe jobs, and export_excel's recency filter treats
# that as "always keep" rather than dropping every Stripe row.)

STRIPE = SiteConfig(
    name="stripe",
    base_url="https://stripe.com/careers/search",
    query_param="query",
    static_params={
        "locations": [
            "North America--United States--Remote in United States",
            "North America--United States--Seattle",
        ],
    },
    pagination=PagePagination(param="page", start=1),
    date_format=None,
    href_prefix="https://stripe.com",
    quote_via=quote_plus,
    selectors=CardSelectors(
        card="li.careers-role-result",
        link="a.careers-role-result__title",
        location="span.careers-role-result__metadata-location",
    ),
)


SITES = {
    "amazon": AMAZON,
    "microsoft": MICROSOFT,
    "stripe": STRIPE,
}
