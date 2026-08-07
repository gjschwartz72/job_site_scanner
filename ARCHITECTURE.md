# job_site_scanner — Architecture

## Flow

```
                         working.ipynb  (driver)
                          |
                          |  utils.scan("amazon", [queries])
                          |  utils.scan("microsoft", [queries])
                          |  utils.scan("stripe", [queries])
                          v
                      utils.py
                +-------------------+
                |  scan()           |---- runs scrape_site() once per query,
                |  export_excel()   |     dedupes by job_id, saves *_jobs_<date>.json
                +-------------------+
                          |
                          v
                   scraper_core.py                       sites.py
                +----------------------+          +---------------------+
                |  scrape_site(config, |<---------|  SITES = {           |
                |    query, max_pages) |  config  |    "amazon": ...,    |
                |                      |          |    "microsoft": ..., |
                |  picks a strategy:   |          |    "stripe": ...     |
                |  - offset pagination |          |  }                   |
                |  - page pagination   |          |                      |
                |  - click pagination  |          |  each entry is a     |
                |  - custom_extractor  |          |  SiteConfig built    |
                +----------+-----------+          |  from site_config.py |
                           |                       +---------------------+
                           v
                    Playwright (Edge)
                           |
                +----------+-----------+-----------+
                v                      v            v
        amazon.jobs website    careers.microsoft   stripe.com/careers
        (card-based HTML,      .com website         (card-based HTML,
         CSS selectors,        (custom_extractor:    CSS selectors,
         offset pagination)     raw <a> tag text-     page-number
                                 parsing, no clean     pagination, no
                                 cards, click          posting date
                                 pagination)           anywhere)
                           |
                           v
              raw job dicts: title, posted, location, href, job_id
                           |
                           v
              _parse_interval_days()  (relative "3 days ago", absolute
                                        "Posted May 21, 2026", or skipped
                                        entirely if date_format is None)
                           |
                           v
              normalized job list  ->  back up to utils.scan()
                           |
                           v
                    pandas DataFrame
                           |
                           v
                   utils.export_excel()   <- keeps rows with unknown
                           |                 (null) interval_days no
                           v                 matter what max_interval is
                     relevance.py
              filter_relevant(df, keywords)   <- title matches DEFAULT_KEYWORDS regex
                           |
                           v
              output/jobs_<date>.xlsx
              (one sheet per site, hyperlinked hrefs)
```

## Files

| File | Role |
|---|---|
| `working.ipynb` | The actual driver — calls `utils.scan()` then `utils.export_excel()` per site |
| `utils.py` | Orchestration: run searches, dedupe, save JSON, filter + write Excel |
| `scraper_core.py` | Generic engine every site runs through — the only place Playwright logic lives |
| `site_config.py` | The `SiteConfig` / `OffsetPagination` / `PagePagination` / `ClickPagination` / `CardSelectors` schema |
| `sites.py` | One `SiteConfig` per site (`SITES` dict) — this is what you edit to add a site |
| `relevance.py` | Keyword regex list that filters job titles down to relevant roles |
| `ADD_SITE_PROMPT.md` | Reusable prompt for onboarding a new site into `sites.py` |

## Two ways a site gets scraped

1. **Card-based (the common case)** — declarative `CardSelectors` in `sites.py`
   (CSS selector for the repeating card, the title/link anchor, date, location).
   `scraper_core.py` does the extraction generically. This is what most ATS
   platforms (Greenhouse, Lever, Workday, iCIMS, and Amazon/Stripe here) look like.
2. **Custom extractor (the escape hatch)** — a small Python function in
   `sites.py` that gets the raw Playwright `page` and returns job dicts
   itself. Used for Microsoft, whose listings aren't in clean repeating
   card elements.

Either way, pagination (`OffsetPagination` item-offset increment,
`PagePagination` page-number increment, or `ClickPagination` next-button
click) and date normalization (`_parse_interval_days`) are handled once,
generically, in `scraper_core.py`. If a site exposes no posting date at all
(Stripe), `date_format` is left `None` and `interval_days` stays null for
every job from that site — `export_excel`'s recency filter treats null as
"keep" rather than dropping the whole site's results.
