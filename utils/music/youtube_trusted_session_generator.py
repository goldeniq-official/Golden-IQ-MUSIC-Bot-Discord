# original code obtained from repository: https://github.com/iv-org/youtube-trusted-session-generator
from __future__ import annotations

import asyncio
import json
import pprint
import traceback
from typing import Any, Optional

# nodriver is a heavy optional dependency (pulls selenium + Chrome) used
# only to refresh the YouTube po_token. On constrained hosts (e.g. small
# Pterodactyl allocations) it is skipped, so the import must be lazy.
try:
    import nodriver
    from nodriver import start, cdp, loop
    _NODRIVER_AVAILABLE = True
    _NODRIVER_IMPORT_ERROR: Optional[BaseException] = None
except ImportError as _e:
    nodriver = None  # type: ignore[assignment]
    start = None  # type: ignore[assignment]
    cdp = None  # type: ignore[assignment]
    loop = None  # type: ignore[assignment]
    _NODRIVER_AVAILABLE = False
    _NODRIVER_IMPORT_ERROR = _e


class Browser:

    def __init__(self):
        self.browser: Any = None
        self.tab: Any = None
        self.task: Optional[asyncio.Task] = None
        self.event = asyncio.Event()
        self.data = {}

    async def start(self, sandbox=True, browser_executable_path=None, **kwargs):
        if not _NODRIVER_AVAILABLE:
            raise RuntimeError(
                "The 'nodriver' package is not installed, so YouTube po_token "
                "cannot be refreshed. Set INSTALL_BROWSER_DEPS=1 (Pterodactyl) "
                "or `pip install nodriver` to enable this feature."
            )
        self.task = asyncio.create_task(self.main_session_gen(sandbox=sandbox, browser_executable_path=browser_executable_path, **kwargs))
        await self.event.wait()
        return self.data

    async def main_session_gen(self, sandbox=True, browser_executable_path=None, **kwargs):
        self.browser = await start(headless=False, sandbox=sandbox, browser_executable_path=browser_executable_path)
        print("[INFO] launching browser.")
        self.tab = self.browser.main_tab
        self.tab.add_handler(cdp.network.RequestWillBeSent, self.send_handler)
        await self.tab.get(f'https://www.youtube.com/embed/{kwargs.get("ytid") or "jNQXAC9IVRw"}')
        await self.tab.wait(cdp.network.RequestWillBeSent)
        button_play = await self.tab.select("#movie_player")
        await button_play.click()
        await self.tab.wait(cdp.network.RequestWillBeSent)
        print("[INFO] waiting additional 30 seconds for slower connections.")
        await self.tab.sleep(30)

    async def send_handler(self, event: cdp.network.RequestWillBeSent):
        if "/youtubei/v1/player" in event.request.url:
            post_data = event.request.post_data
            post_data_json = json.loads(post_data)
            self.data = {
                "visitor_data": post_data_json["context"]["client"]["visitorData"],
                "po_token": post_data_json["serviceIntegrityDimensions"]["poToken"]
            }
            self.browser.stop()
            self.task.cancel()
            self.event.set()
        return

if __name__ == '__main__':

    if not _NODRIVER_AVAILABLE:
        print("nodriver is not installed:", repr(_NODRIVER_IMPORT_ERROR))
    else:
        b = Browser()

        try:
            loop().run_until_complete(b.start(sandbox=False))
        except Exception:
            traceback.print_exc()

        pprint.pprint(b.data)
