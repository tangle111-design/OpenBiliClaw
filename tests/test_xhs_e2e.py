"""Real end-to-end test: XiaohongshuAdapter against a live logged-in Chrome.

Prerequisites (the test skips itself otherwise):

1. Launch Chrome with remote debugging enabled, in a dedicated profile dir:
   ``chrome --remote-debugging-port=9222 --user-data-dir=$HOME/.openbiliclaw-chrome``
2. In that Chrome, log into https://www.xiaohongshu.com once — the cookie
   jar in the custom user-data-dir is what the test relies on.
3. Ensure ``config.toml`` has ``[sources.browser] cdp_url = "http://127.0.0.1:9222"``
   and that the LLM section has a working provider/key.
4. Run: ``pytest -m integration tests/test_xhs_e2e.py -s``

The test exercises the full production code path: Config -> LLMService ->
XiaohongshuAdapter -> BrowserManager(cdp) -> Playwright connect_over_cdp
-> real xiaohongshu.com -> LLM extraction.  No mocks, no fakes, no hooks.
"""

from __future__ import annotations

import asyncio
import socket
import uuid
from urllib.parse import urlparse

import pytest

from openbiliclaw.config import load_config
from openbiliclaw.llm import build_llm_registry
from openbiliclaw.llm.service import LLMService
from openbiliclaw.soul.profile import SoulProfile
from openbiliclaw.sources.protocol import SourceRecipe
from openbiliclaw.sources.web_adapter import XiaohongshuAdapter

_CDP_PROBE_TIMEOUT = 2.0


def _cdp_is_live(cdp_url: str) -> bool:
    """Confirm *something* is listening on the CDP host:port.

    We intentionally do NOT do an HTTP probe: Python's urllib prefers IPv4
    while Node/Playwright prefers IPv6 on macOS, so an HTTP probe can hit
    a *different* Chrome than the one Playwright will connect to (seen
    in the wild when a daily-driver Chrome already owns 127.0.0.1:9222
    and a dedicated CDP Chrome binds only to ::1:9222). A plain TCP
    connect via ``getaddrinfo`` tries every returned address, matching
    Playwright's behaviour.
    """
    if not cdp_url:
        return False
    parsed = urlparse(cdp_url)
    host = parsed.hostname or ""
    port = parsed.port or 9222
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    for family, socktype, proto, _canon, sockaddr in infos:
        try:
            with socket.socket(family, socktype, proto) as sock:
                sock.settimeout(_CDP_PROBE_TIMEOUT)
                sock.connect(sockaddr)
                return True
        except OSError:
            continue
    return False


@pytest.mark.integration
def test_xiaohongshu_adapter_fetch_real_logged_in_chrome() -> None:
    """Drive the real adapter against a real Chrome + real xiaohongshu.com.

    Assertions are deliberately loose: we do not control what shows up in
    the logged-in feed, only that the pipeline returns *some* structurally
    valid items pointing at xiaohongshu.com.
    """
    cfg = load_config()

    cdp_url = cfg.sources.browser_cdp_url
    if not cdp_url:
        pytest.skip("sources.browser.cdp_url not configured")
    if not _cdp_is_live(cdp_url):
        pytest.skip(
            f"Chrome CDP not reachable at {cdp_url} — launch Chrome with "
            "--remote-debugging-port=9222 and log into xiaohongshu first"
        )

    registry = build_llm_registry(cfg)
    llm_service = LLMService(registry=registry, memory=None)

    adapter = XiaohongshuAdapter(
        llm_service=llm_service,
        browser_executable=cfg.bilibili.browser_executable,
        browser_headed=cfg.sources.browser_headed,
        browser_cdp_url=cdp_url,
    )

    recipe = SourceRecipe(
        id=str(uuid.uuid4()),
        source_type="xiaohongshu",
        name="小红书-机械键盘-E2E",
        strategy="search",
        config={"query": "机械键盘"},
        target_share=4,
        enabled=True,
        created_by="user",
    )
    profile = SoulProfile()

    items = asyncio.run(adapter.fetch(recipe, profile, limit=10))

    print(f"\n[E2E] adapter returned {len(items)} items")
    for idx, item in enumerate(items, 1):
        print(
            f"  {idx:02d}  platform={item.source_platform}  id={item.content_id}  "
            f"title={(item.title or '')[:50]}"
        )
        print(f"        url={item.content_url}")

    assert items, "real run returned 0 items — check login state and page"
    assert len(items) <= 10, "limit was not respected"
    for item in items:
        assert item.source_platform == "xiaohongshu", (
            f"expected xiaohongshu, got {item.source_platform!r}"
        )
        assert item.content_id, "content_id must be populated"
        # ``innerText`` on the XHS search page strips href attributes, so
        # ``content_url`` is legitimately empty today; we do NOT assert
        # presence here — only that, if populated, it points at XHS, and
        # that we never leak the literal string "None" (a prior LLM-null
        # coercion bug fixed alongside this test).
        assert item.content_url != "None", (
            f"content_url leaked literal 'None' string: {item.content_url!r}"
        )
        if item.content_url:
            assert "xiaohongshu.com" in item.content_url, (
                f"content_url should point at xiaohongshu: {item.content_url!r}"
            )
        assert item.content_id != "None", (
            f"content_id leaked literal 'None' string: {item.content_id!r}"
        )
