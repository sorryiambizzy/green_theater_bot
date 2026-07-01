# green_theater_bot

Telegram-бот, который ищет раздачи на rutracker.org и присылает в ответ файл
`.torrent` для выбранного релиза.

Автоматически деплоится на VDS при каждом push в `main` через GitHub Actions.

## Как это работает

- Отправляешь боту в Telegram поисковый запрос.
- Бот ищет на rutracker.org (логинясь через headless-браузер + пересылку
  капчи в первый раз или когда сессия протухает) и показывает топ-10
  совпадений кнопками.
- Нажимаешь на результат — получаешь файл `.torrent`.

## Локальная установка

```bash
git clone git@github.com:sorryiambizzy/green_theater_bot.git
cd green_theater_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # заполни TELEGRAM_BOT_TOKEN, RUTRACKER_USERNAME, RUTRACKER_PASSWORD
python3 bot.py
```

## Переменные окружения (`.env`)

- `TELEGRAM_BOT_TOKEN` — от [@BotFather](https://t.me/BotFather)
- `RUTRACKER_USERNAME` / `RUTRACKER_PASSWORD` — твой аккаунт на rutracker.org

## Запуск тестов

```bash
pytest tests/ -v
```

## Деплой

Бот работает как systemd-сервис (`rutracker-bot.service`) на VDS. Push в
`main` автоматически деплоится через GitHub Actions
(`.github/workflows/deploy.yml`): workflow заходит по SSH, делает
`git pull` + `pip install -r requirements.txt` и перезапускает сервис.
`.env` на сервере хранит реальные креды и в репозиторий не входит.

**Требования к серверу:** работает на VDS с 1 vCPU / 1GB RAM (плюс 2GB
swap-файл), но логин через headless Chromium на таком слабом CPU занимает
10-30 секунд. Если настраиваешь сервер с нуля, 2 vCPU комфортнее.

Ручной деплой на новый сервер:

```bash
git clone https://github.com/sorryiambizzy/green_theater_bot.git /opt/rutracker-bot
cd /opt/rutracker-bot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/playwright install --with-deps chromium
cp .env.example .env   # заполни реальными значениями
cp rutracker-bot.service /etc/systemd/system/
systemctl enable --now rutracker-bot
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
