Paste the block below into a chat with Claude Code in this repo, then fill in the
blanks at the bottom with the new site's info.

---

Add a new job site to `job_site_scanner`. Architecture recap: `site_config.py`
defines a `SiteConfig` dataclass; `sites.py` holds one `SiteConfig` per site in
the `SITES` dict; `scraper_core.py` has the generic Playwright engine that
every site runs through (`scrape_site(config, query, max_pages)`); `utils.py`'s
`scan(site_key, queries, max_pages)` calls it and handles dedup/JSON/Excel
export. Adding a normal ATS-style site (Greenhouse, Lever, Workday, iCIMS,
etc.) should only require a new `SiteConfig` entry in `sites.py` — no changes
to the engine.

Steps:
1. Take the URL pattern below and split it into `base_url`, `query_param`
   (which param the search string goes into), and `static_params` (every
   other fixed param — location, distance, remote filter, etc.).
2. Load a real search results page for this site in a browser tool and
   inspect the DOM to find: the repeating job-card selector, the title/link
   anchor, the posted-date element (and whether its text is an absolute date
   like "Posted May 21, 2026" or a relative one like "3 days ago"), and the
   location element. Fill in a `CardSelectors` for it.
3. Figure out the pagination mechanism: an incrementing `offset`/`page`
   query param (`OffsetPagination`), or a "next page" button/click
   (`ClickPagination`). If the page doesn't render job listings in clean
   repeating card elements (rare, but Microsoft's careers site is like this),
   write a small `custom_extractor(page, config, query, max_pages)` instead
   of `CardSelectors` — see `_extract_microsoft` in `sites.py` for the
   pattern to follow.
4. Add the new `SiteConfig` to the `SITES` dict in `sites.py`.
5. Smoke-test it: `python scraper_core.py --site <new_key> --query "data science" --max_pages 1`
   and check the output JSON has sane `title`/`posted`/`interval_days`/`location`/`href` values.
6. Don't touch `scraper_core.py`, `site_config.py`, or `utils.py` unless the
   new site genuinely needs a capability the engine doesn't support yet.

New site info:
- Site name:
- Example search results URL (with a search term already filled in, so the query param is visible):
- Any other notes (login required, weird pagination, etc.):
