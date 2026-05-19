"""TradingView browser automation using Playwright."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config import settings


class TradingViewBrowser:
    """Opens TradingView, searches a symbol, switches timeframe,
    and captures a chart screenshot using Playwright."""

    def __init__(self, headless: bool | None = None) -> None:
        self.headless = headless if headless is not None else settings.browser_headless
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None

    async def __aenter__(self) -> TradingViewBrowser:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()

    async def start(self) -> None:
        """Launch the Playwright browser."""
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self._page = await context.new_page()
        except ImportError:
            raise RuntimeError(
                "playwright is not installed. Run: pip install playwright && playwright install chromium"
            )

    async def stop(self) -> None:
        """Close the browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def search_symbol(self, symbol: str) -> None:
        """Navigate to TradingView and search for a symbol."""
        assert self._page is not None
        base_url = settings.tradingview_url.rstrip("/")
        url = f"{base_url}/chart/?symbol={symbol}"
        try:
            await self._page.goto(url, wait_until="domcontentloaded")
            await self._page.wait_for_timeout(5000)
        except Exception as exc:
            raise RuntimeError(f"Could not navigate to chart for {symbol}: {exc}") from exc

    async def set_timeframe(self, timeframe: str = "1D") -> None:
        """Switch chart timeframe.

        Common values: 1, 5, 15, 30, 60 (minutes), D, W, M.
        """
        assert self._page is not None
        try:
            # Try clicking the timeframe button
            tf_selectors = [
                "[data-name=timeframe-toolbar] button",
                "[class*=timeframe]",
                "button[class*=tv-button]",
            ]
            for sel in tf_selectors:
                try:
                    await self._page.click(sel, timeout=3000)
                    await self._page.wait_for_timeout(500)
                    break
                except Exception:
                    continue

            await self._page.keyboard.type(str(timeframe), delay=30)
            await self._page.wait_for_timeout(1000)
            await self._page.keyboard.press("Enter")
            await self._page.wait_for_timeout(2000)
        except Exception as exc:
            # Non-critical — continue with default timeframe
            pass

    async def capture_screenshot(self, path: str | Path | None = None) -> bytes:
        """Capture a full-page screenshot of the chart.

        Returns the raw PNG bytes. Optionally saves to *path*.
        """
        assert self._page is not None
        await self._page.wait_for_timeout(2000)

        # Try to find the chart container for a more targeted screenshot
        try:
            chart = await self._page.wait_for_selector(
                "[class*=chart-container], [class*=chart-markup-table], canvas",
                timeout=10000,
            )
            if chart:
                screenshot = await chart.screenshot()
            else:
                screenshot = await self._page.screenshot(full_page=False)
        except Exception:
            screenshot = await self._page.screenshot(full_page=False)

        if path:
            Path(path).write_bytes(screenshot)

        return screenshot
