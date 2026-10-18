import logging
from typing import Optional
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_rendered_html(url: str, timeout: float = 30.0) -> Optional[str]:
    """Fetch fully rendered HTML for a given URL using headless Chromium.

    ponytail: Launches fresh browser per fetch; upgrade to persistent browser/context pool if concurrency demands it.
    """
    timeout_ms = timeout * 1000.0
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=DEFAULT_USER_AGENT)
                try:
                    response = await page.goto(
                        url,
                        timeout=timeout_ms,
                        wait_until="domcontentloaded",
                    )
                    if response is None or not response.ok:
                        logger.warning(
                            "Failed to fetch %s: status %s",
                            url,
                            response.status if response else "None",
                        )
                        return None

                    try:
                        await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5000.0))
                    except Exception:
                        pass

                    return await page.content()
                finally:
                    await page.close()
            finally:
                await browser.close()
    except Exception as exc:
        logger.warning("Error fetching rendered HTML for %s: %s", url, exc)
        return None
