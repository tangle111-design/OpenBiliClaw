"""Generic browser automation layer for multi-source content fetching.

Wraps the existing agent-browser CLI to provide a platform-agnostic
browser interface for sources that lack an API.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages browser sessions for non-API content sources.

    Reuses the agent-browser CLI (same as BilibiliBrowser) but
    provides a simpler interface focused on page content extraction
    rather than Bilibili-specific operations.
    """

    def __init__(
        self,
        executable: str = "",
        headed: bool = False,
    ) -> None:
        from openbiliclaw.bilibili.browser import BilibiliBrowser

        self._browser = BilibiliBrowser(
            executable=executable,
            headed=headed,
            cookie="",
        )

    @property
    def is_available(self) -> bool:
        """Whether agent-browser is installed and accessible."""
        return self._browser.is_available

    async def get_page_text(self, url: str) -> str:
        """Navigate to a URL and return the visible page text.

        Args:
            url: The target URL to fetch.

        Returns:
            Extracted text content of the page.

        Raises:
            BrowserCommandError: If the browser command fails.
        """
        return await self._browser.get_page_content(url)

    async def close(self) -> None:
        """Close the browser session."""
        await self._browser.close()
