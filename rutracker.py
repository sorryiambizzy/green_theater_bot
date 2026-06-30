import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable
from urllib.parse import urlparse, parse_qs

BASE_URL = "https://rutracker.org/forum"


@dataclass
class SearchResult:
    topic_id: str
    title: str
    size: str
    seeders: int


async def playwright_login(
    username: str,
    password: str,
    captcha_callback: Callable[[bytes], Awaitable[str]],
) -> dict:
    """Login via headless browser running in a thread to avoid event loop conflicts."""
    import asyncio
    import time
    from playwright.sync_api import sync_playwright

    loop = asyncio.get_running_loop()
    captcha_queue: asyncio.Queue = asyncio.Queue()
    code_queue: asyncio.Queue = asyncio.Queue()
    result_holder: list = [None, None]  # [cookies, exception]

    def run_sync():
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page = ctx.new_page()
                page.goto(f"{BASE_URL}/login.php", wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)

                while True:
                    # Refill credentials on every iteration — password is cleared after failed captcha
                    page.locator('input[name="login_username"]').nth(1).fill(username)
                    page.locator('input[name="login_password"]').nth(1).fill(password)

                    cap_img = page.locator('img[src*="/captcha/"]')
                    if not cap_img.is_visible():
                        break

                    screenshot = cap_img.screenshot()
                    asyncio.run_coroutine_threadsafe(captcha_queue.put(screenshot), loop).result()
                    code = asyncio.run_coroutine_threadsafe(code_queue.get(), loop).result(timeout=300)

                    page.locator('input[name^="cap_code_"]').fill(code)
                    page.locator('input[name="login"]').last.click()
                    time.sleep(5)

                    cookies_now = {c["name"]: c["value"] for c in ctx.cookies()}
                    if "bb_session" in cookies_now:
                        browser.close()
                        result_holder[0] = cookies_now
                        asyncio.run_coroutine_threadsafe(captcha_queue.put(None), loop)
                        return

                page.locator('input[name="login"]').last.click()
                time.sleep(3)
                result_holder[0] = {c["name"]: c["value"] for c in ctx.cookies()}
                browser.close()
        except Exception as e:
            result_holder[1] = e
        finally:
            asyncio.run_coroutine_threadsafe(captcha_queue.put(None), loop)

    executor_future = loop.run_in_executor(None, run_sync)

    while True:
        item = await captcha_queue.get()
        if item is None:
            break
        code = await captcha_callback(item)
        await code_queue.put(code)

    await asyncio.wrap_future(executor_future)

    if result_holder[1]:
        raise result_holder[1]
    return result_holder[0] or {}


class RutrackerClient:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        })
        self._logged_in = False

    def set_session_cookies(self, cookies: dict) -> None:
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain="rutracker.org")
        if "bb_session" in cookies:
            self._logged_in = True

    def _ensure_logged_in(self) -> None:
        if not self._logged_in:
            raise RuntimeError("Not logged in")

    def search(self, query: str) -> list[SearchResult]:
        self._ensure_logged_in()
        resp = self.session.get(
            f"{BASE_URL}/tracker.php",
            params={"nm": query},
        )
        resp.raise_for_status()
        if "login.php" in resp.url:
            self._logged_in = False
            raise RuntimeError("Session expired")
        return self._parse_search_results(resp.text)

    def get_torrent(self, topic_id: str) -> bytes:
        self._ensure_logged_in()
        resp = self.session.get(
            f"{BASE_URL}/dl.php",
            params={"t": topic_id},
        )
        if "login.php" in resp.url:
            self._logged_in = False
            raise RuntimeError("Session expired")
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "")
        if "bittorrent" not in ct and not resp.content.startswith(b"d"):
            raise ValueError(f"Response is not a torrent file (Content-Type: {ct})")
        return resp.content

    def get_magnet(self, topic_id: str) -> Optional[str]:
        self._ensure_logged_in()
        resp = self.session.get(
            f"{BASE_URL}/viewtopic.php",
            params={"t": topic_id},
        )
        if "login.php" in resp.url:
            self._logged_in = False
            raise RuntimeError("Session expired")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        link = soup.find("a", class_="magnet-link")
        if link:
            return link.get("href")
        return None

    def _parse_search_results(self, html: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        table = soup.find("table", id="tor-tbl")
        if not table:
            return results
        for row in table.find_all("tr", class_="tCenter"):
            try:
                title_cell = row.find("td", class_="t-title")
                if not title_cell:
                    continue
                link = title_cell.find("a", class_="tLink")
                if not link:
                    continue
                href = link.get("href", "")
                parsed = urlparse(href)
                topic_id = parse_qs(parsed.query).get("t", [""])[0]
                if not topic_id:
                    continue
                title = link.text.strip()
                size_cell = row.find("td", class_="tor-size")
                size = size_cell.text.strip() if size_cell else "?"
                seeds_el = row.find("b", class_=re.compile(r"seed(med|good|bad|null)"))
                seeders = int(seeds_el.text.strip()) if seeds_el else 0
                results.append(SearchResult(
                    topic_id=topic_id,
                    title=title,
                    size=size,
                    seeders=seeders,
                ))
            except Exception:
                continue
        return results[:10]
