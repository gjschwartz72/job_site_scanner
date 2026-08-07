"""Declarative config schema for a scrapeable job site.

A new "normal" ATS-style site (Greenhouse, Lever, Workday, iCIMS, etc.) should
only need a SiteConfig entry in sites.py -- no new scraping code. custom_extractor
is an escape hatch for sites whose job listings aren't in clean repeating cards.
"""
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlencode, quote


@dataclass
class OffsetPagination:
    """Page N is fetched by re-requesting the URL with an incrementing item-offset param (0, 10, 20, ...)."""
    param: str
    page_size: int


@dataclass
class PagePagination:
    """Page N is fetched by re-requesting the URL with an incrementing page-number param (1, 2, 3, ...)."""
    param: str
    start: int = 1


@dataclass
class ClickPagination:
    """Page N is reached by clicking a 'next' button in the loaded page.

    disabled_attr is checked for presence/truthiness, not just equality to "true" --
    this covers both aria-disabled="true" and plain HTML boolean `disabled` attributes.
    """
    next_button_selector: str
    disabled_attr: str = "aria-disabled"
    wait_ms: int = 1000


@dataclass
class CardSelectors:
    """Field selectors, each evaluated relative to a single job-card element."""
    card: str                                   # repeating job card container
    link: str                                   # anchor: provides href, and title text if `title` unset
    title: Optional[str] = None                 # separate title element, if not the link itself
    date: Optional[str] = None
    location: Optional[str] = None
    job_id_attr: Optional[tuple] = None         # (selector, attribute) e.g. ("div.job", "data-job-id")


@dataclass
class SiteConfig:
    name: str
    base_url: str
    query_param: str                            # URL param the search string goes into
    static_params: dict                         # fixed filter params (location, distance, etc.); list values become repeated params
    pagination: object                          # OffsetPagination | PagePagination | ClickPagination
    date_format: Optional[str] = None           # "relative", "absolute:<strptime format>", or None if the site exposes no posting date
    selectors: Optional[CardSelectors] = None   # required unless custom_extractor is set
    custom_extractor: Optional[Callable] = None  # fn(page, config, query, max_pages) -> list[dict], for non-card layouts
    href_prefix: str = ""                       # prepended to hrefs that start with "/"
    quote_via: Callable = quote
    goto_wait_ms: int = 3000

    def build_url(self, query, page_index=0):
        params = {**self.static_params, self.query_param: query}
        if isinstance(self.pagination, OffsetPagination):
            params[self.pagination.param] = str(page_index * self.pagination.page_size)
        elif isinstance(self.pagination, PagePagination):
            params[self.pagination.param] = str(self.pagination.start + page_index)
        return f"{self.base_url}?{urlencode(params, doseq=True, quote_via=self.quote_via)}"


def is_disabled(locator, attr):
    """True if `attr` is present and not explicitly "false" -- covers both
    aria-disabled="true" and plain HTML boolean `disabled` (which Playwright
    reports as an empty string when present)."""
    val = locator.get_attribute(attr)
    return val is not None and val.lower() != "false"
