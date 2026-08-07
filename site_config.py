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
    """Page N is fetched by re-requesting the URL with an incrementing offset param."""
    param: str
    page_size: int


@dataclass
class ClickPagination:
    """Page N is reached by clicking a 'next' button in the loaded page."""
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
    static_params: dict                         # fixed filter params (location, distance, etc.)
    pagination: object                          # OffsetPagination | ClickPagination
    date_format: str                            # "relative" or "absolute:<strptime format>"
    selectors: Optional[CardSelectors] = None   # required unless custom_extractor is set
    custom_extractor: Optional[Callable] = None  # fn(page, config, query, max_pages) -> list[dict], for non-card layouts
    href_prefix: str = ""                       # prepended to hrefs that start with "/"
    quote_via: Callable = quote
    goto_wait_ms: int = 3000

    def build_url(self, query, offset=0):
        params = {**self.static_params, self.query_param: query}
        if isinstance(self.pagination, OffsetPagination):
            params[self.pagination.param] = str(offset)
        return f"{self.base_url}?{urlencode(params, quote_via=self.quote_via)}"
