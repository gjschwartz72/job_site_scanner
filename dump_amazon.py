from playwright.sync_api import sync_playwright

URL = "https://www.amazon.jobs/en/search?offset=0&result_limit=10&sort=recent&distanceType=Mi&radius=24km&loc_group_id=seattle-metro&latitude=&longitude=&loc_group_id=seattle-metro&loc_query=Greater%20Seattle%20Area%2C%20WA%2C%20United%20States&base_query=data%20science%20&city=&country=&region=&county=&query_options=&"

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=False)
    page = browser.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    with open("amazon_dump.html", "w", encoding="utf-8") as f:
        f.write(page.content())

    browser.close()

print("Saved amazon_dump.html")
