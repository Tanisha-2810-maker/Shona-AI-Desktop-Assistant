from playwright.sync_api import sync_playwright

import webbrowser
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

def google_search(query: str):
    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        page.goto("https://www.google.com")

        page.locator("textarea").fill(query)

        page.keyboard.press("Enter")

        page.wait_for_timeout(3000)

        return browser

def search_web_and_collect(query: str) -> dict:
    """
    Opens the search in the user's normal browser and uses a temporary
    headless Playwright browser to collect readable search-result text.

    Returns:
        {
            "query": str,
            "text": str,
            "url": str
        }
    """

    clean_query = query.strip()

    if not clean_query:
        raise ValueError("The search query cannot be empty.")

    search_url = (
        "https://www.google.com/search?q="
        + quote_plus(clean_query)
    )

    # Keep the results visible for the user.
    webbrowser.open(search_url)

    extracted_text = ""

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True
            )

            page = browser.new_page(
                viewport={
                    "width": 1280,
                    "height": 900,
                }
            )

            page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            page.wait_for_timeout(2000)

            extracted_text = page.locator(
                "body"
            ).inner_text(
                timeout=10000
            )

            browser.close()

    except Exception as error:
        print(f"Google extraction error: {error}")

    # Fallback when Google shows a consent or restricted page.
    if len(extracted_text.strip()) < 150:
        fallback_url = (
            "https://html.duckduckgo.com/html/?q="
            + quote_plus(clean_query)
        )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True
                )

                page = browser.new_page()

                page.goto(
                    fallback_url,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                extracted_text = page.locator(
                    "body"
                ).inner_text(
                    timeout=10000
                )

                browser.close()

        except Exception as error:
            print(f"Fallback search error: {error}")

    if not extracted_text.strip():
        extracted_text = (
            "The browser search opened successfully, but Shona "
            "could not extract readable search-result text."
        )

    return {
        "query": clean_query,
        "text": extracted_text[:18000],
        "url": search_url,
    }