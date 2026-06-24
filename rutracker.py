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
