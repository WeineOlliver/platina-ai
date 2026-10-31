import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from src.services.browser import fetch_rendered_html


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_fetch_rendered_html_mock_success():
    mock_response = MagicMock(ok=True, status=200)
    mock_page = AsyncMock()
    mock_page.goto.return_value = mock_response
    mock_page.content.return_value = "<html><body><h1>Mock Title</h1></body></html>"
    mock_page.wait_for_load_state.return_value = None
    mock_page.close.return_value = None

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page
    mock_browser.close.return_value = None

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_playwright
    mock_cm.__aexit__.return_value = None

    with patch("src.services.browser.async_playwright", return_value=mock_cm):
        result = await fetch_rendered_html("https://example.com", timeout=5.0)

    assert result == "<html><body><h1>Mock Title</h1></body></html>"
    mock_page.goto.assert_awaited_once_with(
        "https://example.com",
        timeout=5000.0,
        wait_until="domcontentloaded",
    )
    mock_page.close.assert_awaited_once()
    mock_browser.close.assert_awaited_once()


@pytest.mark.anyio
async def test_fetch_rendered_html_mock_http_error():
    mock_response = MagicMock(ok=False, status=403)
    mock_page = AsyncMock()
    mock_page.goto.return_value = mock_response
    mock_page.close.return_value = None

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page
    mock_browser.close.return_value = None

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_playwright
    mock_cm.__aexit__.return_value = None

    with patch("src.services.browser.async_playwright", return_value=mock_cm):
        result = await fetch_rendered_html("https://example.com/blocked", timeout=5.0)

    assert result is None
    mock_page.close.assert_awaited_once()
    mock_browser.close.assert_awaited_once()


@pytest.mark.anyio
async def test_fetch_rendered_html_mock_timeout():
    mock_page = AsyncMock()
    mock_page.goto.side_effect = PlaywrightTimeoutError("Navigation timeout")
    mock_page.close.return_value = None

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page
    mock_browser.close.return_value = None

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_playwright
    mock_cm.__aexit__.return_value = None

    with patch("src.services.browser.async_playwright", return_value=mock_cm):
        result = await fetch_rendered_html("https://example.com/slow", timeout=1.0)

    assert result is None
    mock_page.close.assert_awaited_once()
    mock_browser.close.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.integration
async def test_fetch_rendered_html_live_probe():
    html = None
    try:
        html = await fetch_rendered_html("https://httpbin.org/html", timeout=20.0)
    except Exception as e:
        pytest.skip(f"Live browser probe unavailable in environment: {e}")
    if html is None:
        pytest.skip("Live browser probe failed or Chromium not installed")
    assert "<html" in html.lower()
    assert "moby-dick" in html.lower()
