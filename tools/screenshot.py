"""Screenshot capture — saves screenshots to the configured directory."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config import settings


class ScreenshotCapture:
    """Utility to save binary screenshot data to disk with metadata."""

    def __init__(self) -> None:
        self._output_dir = settings.browser_screenshot_dir
        if self._output_dir:
            self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def output_dir(self) -> Path:
        assert self._output_dir is not None
        return self._output_dir

    async def save(self, image_data: bytes, symbol: str, label: str = "") -> Path:
        """Save a PNG screenshot to disk and return the path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_symbol = symbol.replace("/", "_").replace(" ", "_")
        filename = f"{safe_symbol}_{label}_{timestamp}.png" if label else f"{safe_symbol}_{timestamp}.png"
        dest = self.output_dir / filename
        dest.write_bytes(image_data)
        return dest

    def get_latest(self, symbol: str) -> Path | None:
        """Return the most recent screenshot for a symbol."""
        screenshots = sorted(self.output_dir.glob(f"{symbol}_*.png"))
        return screenshots[-1] if screenshots else None
