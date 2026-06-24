import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional

BASE_URL = "https://rutracker.org/forum"


@dataclass
class SearchResult:
    topic_id: str
    title: str
    size: str
    seeders: int


class RutrackerClient:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })
        self._logged_in = False

    def login(self) -> None:
        resp = self.session.post(
            f"{BASE_URL}/login.php",
            data={
                "login_username": self.username,
                "login_password": self.password,
                "login": "вход",
            },
            allow_redirects=True,
        )
        resp.raise_for_status()
        if "bb_session" not in self.session.cookies:
            raise ValueError("Login failed: no bb_session cookie")
        self._logged_in = True

    def _ensure_logged_in(self) -> None:
        if not self._logged_in:
            self.login()

    def search(self, query: str) -> list[SearchResult]:
        self._ensure_logged_in()
        resp = self.session.get(
            f"{BASE_URL}/tracker.php",
            params={"nm": query},
        )
        resp.raise_for_status()
        if "login.php" in resp.url:
            self._logged_in = False
            self.login()
            resp = self.session.get(f"{BASE_URL}/tracker.php", params={"nm": query})
            resp.raise_for_status()
        return self._parse_search_results(resp.text)

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
                topic_id = href.split("t=")[-1]
                title = link.text.strip()
                size_cell = row.find("td", class_="tor-size")
                size = size_cell.text.strip() if size_cell else "?"
                seeds_el = row.find("b", class_="seedmed")
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
