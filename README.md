# green_theater_bot

Telegram bot that searches rutracker.org and sends back the `.torrent` file
for the release you pick.

## How it works

- Send a search term to the bot in Telegram.
- The bot searches rutracker.org (logging in via a headless browser + captcha
  relay the first time, or whenever the session expires) and shows the top
  10 matches as buttons.
- Tap a result, get the `.torrent` file back.

## Local setup

```bash
git clone git@github.com:sorryiambizzy/green_theater_bot.git
cd green_theater_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, RUTRACKER_USERNAME, RUTRACKER_PASSWORD
python3 bot.py
```

## Environment variables (`.env`)

- `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
- `RUTRACKER_USERNAME` / `RUTRACKER_PASSWORD` — your rutracker.org account

## Running tests

```bash
pytest tests/ -v
```

## Deployment

The bot runs as a systemd service (`rutracker-bot.service`) on a VDS. Pushes
to `main` auto-deploy via GitHub Actions (`.github/workflows/deploy.yml`):
the workflow SSHes in, runs `git pull` + `pip install -r requirements.txt`,
and restarts the service. The server's `.env` holds the real credentials and
isn't part of the repo.

**Server sizing:** works on a 1 vCPU / 1GB RAM VDS (with a 2GB swap file),
but logging in via headless Chromium takes 10-30s on that little CPU. 2
vCPUs is more comfortable if you're setting this up fresh.

To deploy manually to a fresh server:

```bash
git clone https://github.com/sorryiambizzy/green_theater_bot.git /opt/rutracker-bot
cd /opt/rutracker-bot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/playwright install --with-deps chromium
cp .env.example .env   # fill in real values
cp rutracker-bot.service /etc/systemd/system/
systemctl enable --now rutracker-bot
```

## License

MIT — see [LICENSE](LICENSE).
