# Rutracker Telegram Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram-бот, который ищет торренты на rutracker.org и отправляет .torrent файл + magnet-ссылку любому пользователю.

**Architecture:** Один Python-процесс: Telegram-бот принимает запросы, скрапер (requests + BeautifulSoup) логинится на rutracker и выполняет поиск/скачивание, результаты отдаются обратно в Telegram. Бот stateless, без базы данных.

**Tech Stack:** Python 3.11+, python-telegram-bot 20+, requests, beautifulsoup4, python-dotenv, pytest

## Global Constraints

- Python 3.11+
- `python-telegram-bot` версии 20+ (async API, не v13)
- Ошибка недоступности rutracker → текст `"Rutracker временно недоступен"`
- Нет результатов → текст `"По запросу ничего не найдено"`
- Бот открыт для всех пользователей Telegram, без авторизации
- Секреты только в `.env`, не в коде

---

### Task 1: Scaffolding — структура проекта и конфигурация

**Files:**
- Create: `rutracker-bot/requirements.txt`
- Create: `rutracker-bot/.env.example`
- Create: `rutracker-bot/config.py`
- Create: `rutracker-bot/tests/__init__.py`

**Interfaces:**
- Produces: `config.BOT_TOKEN: str`, `config.RUTRACKER_USERNAME: str`, `config.RUTRACKER_PASSWORD: str`

- [ ] **Step 1: Создать директорию проекта и структуру**

```bash
mkdir -p rutracker-bot/tests
cd rutracker-bot
```

- [ ] **Step 2: Создать `requirements.txt`**

```
python-telegram-bot==20.7
requests==2.31.0
beautifulsoup4==4.12.3
python-dotenv==1.0.1
pytest==8.1.1
```

- [ ] **Step 3: Создать `.env.example`**

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
RUTRACKER_USERNAME=your_rutracker_login
RUTRACKER_PASSWORD=your_rutracker_password
```

- [ ] **Step 4: Создать `config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RUTRACKER_USERNAME = os.environ["RUTRACKER_USERNAME"]
RUTRACKER_PASSWORD = os.environ["RUTRACKER_PASSWORD"]
```

- [ ] **Step 5: Создать `.env` из шаблона и заполнить реальными данными**

```bash
cp .env.example .env
# заполни BOT_TOKEN, RUTRACKER_USERNAME, RUTRACKER_PASSWORD
```

Получить токен бота: написать @BotFather в Telegram → `/newbot`.

- [ ] **Step 6: Установить зависимости**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 7: Убедиться что конфиг загружается**

```bash
python3 -c "import config; print('OK:', config.BOT_TOKEN[:10])"
```

Ожидаем: `OK: <первые 10 символов токена>`

- [ ] **Step 8: Commit**

```bash
git init
echo "venv/" > .gitignore
echo ".env" >> .gitignore
echo "__pycache__/" >> .gitignore
git add requirements.txt .env.example config.py .gitignore tests/__init__.py
git commit -m "feat: project scaffolding and config"
```

---

### Task 2: RutrackerClient — авторизация

**Files:**
- Create: `rutracker-bot/rutracker.py`
- Create: `rutracker-bot/tests/test_rutracker.py`

**Interfaces:**
- Produces:
  - `RutrackerClient(username: str, password: str)`
  - `client.login() -> None` — выбрасывает `ValueError("Login failed")` если нет cookie `bb_session`
  - `client._logged_in: bool`
  - `client._ensure_logged_in() -> None`

- [ ] **Step 1: Написать failing-тест на успешный логин**

Создать `tests/test_rutracker.py`:

```python
from unittest.mock import patch, MagicMock
import pytest
from rutracker import RutrackerClient


def make_client():
    return RutrackerClient("testuser", "testpass")


@patch("rutracker.requests.Session")
def test_login_success(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_session.post.return_value = MagicMock()
    mock_session.cookies = {"bb_session": "abc123"}

    client = make_client()
    client.login()

    assert client._logged_in is True
    mock_session.post.assert_called_once()


@patch("rutracker.requests.Session")
def test_login_failure_no_cookie(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_session.post.return_value = MagicMock()
    mock_session.cookies = {}

    client = make_client()
    with pytest.raises(ValueError, match="Login failed"):
        client.login()

    assert client._logged_in is False
```

- [ ] **Step 2: Запустить тест, убедиться что падает**

```bash
pytest tests/test_rutracker.py::test_login_success -v
```

Ожидаем: `FAILED` с `ModuleNotFoundError: No module named 'rutracker'`

- [ ] **Step 3: Написать минимальную реализацию логина в `rutracker.py`**

```python
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
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

```bash
pytest tests/test_rutracker.py -v
```

Ожидаем: 2 теста `PASSED`

- [ ] **Step 5: Commit**

```bash
git add rutracker.py tests/test_rutracker.py
git commit -m "feat: RutrackerClient login"
```

---

### Task 3: RutrackerClient — поиск

**Files:**
- Modify: `rutracker-bot/rutracker.py` — добавить `search()` и `_parse_search_results()`
- Modify: `rutracker-bot/tests/test_rutracker.py` — добавить тесты на поиск

**Interfaces:**
- Consumes: `RutrackerClient`, `SearchResult`, `client._ensure_logged_in()`, `client._logged_in`
- Produces:
  - `client.search(query: str) -> list[SearchResult]` — максимум 10 результатов
  - `client._parse_search_results(html: str) -> list[SearchResult]`

- [ ] **Step 1: Написать тесты на парсинг результатов**

Добавить в `tests/test_rutracker.py`:

```python
SEARCH_HTML = """
<table id="tor-tbl">
  <tbody>
    <tr class="tCenter">
      <td class="t-title">
        <a class="tLink" href="/forum/viewtopic.php?t=12345">
          Интерстеллар / Interstellar (2014) BDRip 1080p
        </a>
      </td>
      <td class="tor-size" data-ts_text="16344498176">15.2 GB</td>
      <td><b class="seedmed">142</b></td>
    </tr>
    <tr class="tCenter">
      <td class="t-title">
        <a class="tLink" href="/forum/viewtopic.php?t=67890">
          Интерстеллар / Interstellar (2014) HDRip 720p
        </a>
      </td>
      <td class="tor-size" data-ts_text="5000000000">4.8 GB</td>
      <td><b class="seedmed">89</b></td>
    </tr>
  </tbody>
</table>
"""

EMPTY_HTML = "<html><body><p>No results</p></body></html>"


def test_parse_search_results_returns_results():
    client = make_client()
    results = client._parse_search_results(SEARCH_HTML)
    assert len(results) == 2
    assert results[0].topic_id == "12345"
    assert results[0].title == "Интерстеллар / Interstellar (2014) BDRip 1080p"
    assert results[0].size == "15.2 GB"
    assert results[0].seeders == 142


def test_parse_search_results_empty_page():
    client = make_client()
    results = client._parse_search_results(EMPTY_HTML)
    assert results == []


def test_parse_search_results_caps_at_10():
    row = """
    <tr class="tCenter">
      <td class="t-title">
        <a class="tLink" href="/forum/viewtopic.php?t={i}">Title {i}</a>
      </td>
      <td class="tor-size">1 GB</td>
      <td><b class="seedmed">10</b></td>
    </tr>"""
    rows = "".join(row.format(i=i) for i in range(15))
    html = f'<table id="tor-tbl"><tbody>{rows}</tbody></table>'
    client = make_client()
    results = client._parse_search_results(html)
    assert len(results) == 10


@patch("rutracker.requests.Session")
def test_search_redirects_to_login_triggers_relogin(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    # First get: redirected to login page
    redirect_response = MagicMock()
    redirect_response.url = "https://rutracker.org/forum/login.php"
    redirect_response.text = EMPTY_HTML

    # After re-login: normal response
    normal_response = MagicMock()
    normal_response.url = "https://rutracker.org/forum/tracker.php"
    normal_response.text = SEARCH_HTML

    mock_session.get.side_effect = [redirect_response, normal_response]
    mock_session.post.return_value = MagicMock()
    mock_session.cookies = {"bb_session": "abc123"}

    client = make_client()
    client._logged_in = True
    results = client.search("Интерстеллар")

    assert mock_session.post.called  # re-login happened
    assert len(results) == 2
```

- [ ] **Step 2: Запустить, убедиться что тесты падают**

```bash
pytest tests/test_rutracker.py -k "parse_search or test_search" -v
```

Ожидаем: `FAILED` — метод `_parse_search_results` не существует

- [ ] **Step 3: Добавить `search()` и `_parse_search_results()` в `rutracker.py`**

Добавить методы в класс `RutrackerClient` после `_ensure_logged_in`:

```python
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
```

- [ ] **Step 4: Запустить все тесты**

```bash
pytest tests/test_rutracker.py -v
```

Ожидаем: все тесты `PASSED`

- [ ] **Step 5: Commit**

```bash
git add rutracker.py tests/test_rutracker.py
git commit -m "feat: rutracker search and result parsing"
```

---

### Task 4: RutrackerClient — скачивание .torrent и magnet-ссылки

**Files:**
- Modify: `rutracker-bot/rutracker.py` — добавить `get_torrent()` и `get_magnet()`
- Modify: `rutracker-bot/tests/test_rutracker.py` — добавить тесты

**Interfaces:**
- Consumes: `RutrackerClient`, `client._ensure_logged_in()`, `client._logged_in`, `client.login()`
- Produces:
  - `client.get_torrent(topic_id: str) -> bytes`
  - `client.get_magnet(topic_id: str) -> Optional[str]`

- [ ] **Step 1: Написать тесты**

Добавить в `tests/test_rutracker.py`:

```python
TOPIC_HTML_WITH_MAGNET = """
<html><body>
<a class="magnet-link" href="magnet:?xt=urn:btih:abc123def456&dn=Interstellar">
  Magnet link
</a>
</body></html>
"""

TOPIC_HTML_NO_MAGNET = "<html><body><p>No magnet here</p></body></html>"

FAKE_TORRENT_BYTES = b"d8:announce35:http://retracker.local/announce13:announce-listlee"


@patch("rutracker.requests.Session")
def test_get_torrent_returns_bytes(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_response = MagicMock()
    mock_response.url = "https://rutracker.org/forum/dl.php?t=12345"
    mock_response.content = FAKE_TORRENT_BYTES
    mock_session.get.return_value = mock_response

    client = make_client()
    client._logged_in = True
    result = client.get_torrent("12345")

    assert result == FAKE_TORRENT_BYTES
    mock_session.get.assert_called_once()
    call_args = mock_session.get.call_args
    assert "dl.php" in call_args.args[0]


@patch("rutracker.requests.Session")
def test_get_magnet_returns_link(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_response = MagicMock()
    mock_response.text = TOPIC_HTML_WITH_MAGNET
    mock_session.get.return_value = mock_response

    client = make_client()
    client._logged_in = True
    magnet = client.get_magnet("12345")

    assert magnet == "magnet:?xt=urn:btih:abc123def456&dn=Interstellar"


@patch("rutracker.requests.Session")
def test_get_magnet_returns_none_if_not_found(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_response = MagicMock()
    mock_response.text = TOPIC_HTML_NO_MAGNET
    mock_session.get.return_value = mock_response

    client = make_client()
    client._logged_in = True
    magnet = client.get_magnet("12345")

    assert magnet is None
```

- [ ] **Step 2: Запустить, убедиться что тесты падают**

```bash
pytest tests/test_rutracker.py -k "get_torrent or get_magnet" -v
```

Ожидаем: `FAILED` — методы не определены

- [ ] **Step 3: Добавить методы в `rutracker.py`**

Добавить в конец класса `RutrackerClient`:

```python
    def get_torrent(self, topic_id: str) -> bytes:
        self._ensure_logged_in()
        resp = self.session.get(
            f"{BASE_URL}/dl.php",
            params={"t": topic_id},
        )
        if "login.php" in resp.url:
            self._logged_in = False
            self.login()
            resp = self.session.get(f"{BASE_URL}/dl.php", params={"t": topic_id})
        resp.raise_for_status()
        return resp.content

    def get_magnet(self, topic_id: str) -> Optional[str]:
        self._ensure_logged_in()
        resp = self.session.get(
            f"{BASE_URL}/viewtopic.php",
            params={"t": topic_id},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        link = soup.find("a", class_="magnet-link")
        if link:
            return link.get("href")
        return None
```

- [ ] **Step 4: Запустить все тесты**

```bash
pytest tests/test_rutracker.py -v
```

Ожидаем: все тесты `PASSED`

- [ ] **Step 5: Commit**

```bash
git add rutracker.py tests/test_rutracker.py
git commit -m "feat: get_torrent and get_magnet"
```

---

### Task 5: Telegram-бот — обработчики

**Files:**
- Create: `rutracker-bot/bot.py`

**Interfaces:**
- Consumes:
  - `config.BOT_TOKEN: str`, `config.RUTRACKER_USERNAME: str`, `config.RUTRACKER_PASSWORD: str`
  - `RutrackerClient(username, password)`
  - `client.search(query: str) -> list[SearchResult]`
  - `client.get_torrent(topic_id: str) -> bytes`
  - `client.get_magnet(topic_id: str) -> Optional[str]`
  - `SearchResult.topic_id: str`, `.title: str`, `.size: str`, `.seeders: int`

- [ ] **Step 1: Написать `bot.py`**

```python
import io
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
from rutracker import RutrackerClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = RutrackerClient(config.RUTRACKER_USERNAME, config.RUTRACKER_PASSWORD)


async def start(update: Update, context) -> None:
    await update.message.reply_text(
        "Отправь мне название фильма, сериала или игры — найду торрент на rutracker"
    )


async def handle_search(update: Update, context) -> None:
    query = update.message.text.strip()
    status_msg = await update.message.reply_text("Ищу...")

    try:
        results = client.search(query)
    except Exception:
        logger.exception("Search failed for query: %s", query)
        await status_msg.edit_text("Rutracker временно недоступен")
        return

    if not results:
        await status_msg.edit_text("По запросу ничего не найдено")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"{r.title[:55]} | {r.size} | {r.seeders} сид",
            callback_data=r.topic_id,
        )]
        for r in results
    ]
    await status_msg.edit_text(
        f"Найдено {len(results)} результатов:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_selection(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    topic_id = query.data

    await query.edit_message_text("Скачиваю...")

    try:
        torrent_bytes = client.get_torrent(topic_id)
        magnet = client.get_magnet(topic_id)
    except Exception:
        logger.exception("Download failed for topic_id: %s", topic_id)
        await query.edit_message_text("Rutracker временно недоступен")
        return

    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=io.BytesIO(torrent_bytes),
        filename=f"{topic_id}.torrent",
    )
    if magnet:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"`{magnet}`",
            parse_mode="Markdown",
        )


def main() -> None:
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Запустить бота локально и проверить вручную**

```bash
source venv/bin/activate
python3 bot.py
```

Ожидаем: `INFO - Application started` без ошибок.

Проверить в Telegram:
1. Отправить `/start` → ответ с инструкцией
2. Отправить `Интерстеллар 2014` → список результатов кнопками
3. Нажать кнопку → .torrent файл + magnet-ссылка
4. Отправить `xyzxyzxyz_несуществующее` → `По запросу ничего не найдено`

- [ ] **Step 3: Commit**

```bash
git add bot.py
git commit -m "feat: telegram bot handlers"
```

---

### Task 6: Деплой на VPS

**Files:**
- Create: `rutracker-bot/rutracker-bot.service`

**Interfaces:**
- Consumes: всё из предыдущих задач

- [ ] **Step 1: Создать systemd unit-файл `rutracker-bot.service`**

```ini
[Unit]
Description=Rutracker Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/rutracker-bot
ExecStart=/opt/rutracker-bot/venv/bin/python bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Загрузить проект на VPS**

Выполнить на локальной машине (заменить `USER` и `HOST`):

```bash
rsync -avz --exclude='.env' --exclude='venv/' --exclude='__pycache__/' \
  rutracker-bot/ USER@HOST:/opt/rutracker-bot/
```

- [ ] **Step 3: Настроить окружение на VPS**

```bash
ssh USER@HOST

cd /opt/rutracker-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Создать .env с реальными данными
nano .env
```

- [ ] **Step 4: Установить и запустить systemd-сервис**

```bash
sudo cp /opt/rutracker-bot/rutracker-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rutracker-bot
sudo systemctl start rutracker-bot
sudo systemctl status rutracker-bot
```

Ожидаем: `active (running)`

- [ ] **Step 5: Проверить логи**

```bash
sudo journalctl -u rutracker-bot -f
```

Ожидаем: `INFO - Application started` без ошибок.

- [ ] **Step 6: Финальный commit**

```bash
git add rutracker-bot.service
git commit -m "feat: systemd deployment config"
```

---

## Итог

После Task 6 бот запущен на VPS, принимает запросы от всех пользователей и возвращает .torrent файл + magnet-ссылку. Rutracker доступен с VPS напрямую без VPN.
