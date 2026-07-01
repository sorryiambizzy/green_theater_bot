# CLAUDE.md

## What this is

A Telegram bot that searches rutracker.org and sends back the `.torrent` file
for the release the user picks. Bridges python-telegram-bot (v20) to
rutracker.org.

## Why login uses Playwright, not plain `requests`

rutracker.org's login form requires solving an image captcha before it will
set the `bb_session` cookie. A bare `requests.post()` to the login endpoint
can't solve a captcha. `playwright_login()` in `rutracker.py` drives a real
headless Chromium session: it screenshots the captcha image and relays it to
the user over Telegram to get the typed code back, then resubmits the form.

## The threading model in `playwright_login`

Playwright's sync API can't run inside the bot's asyncio event loop directly,
so the browser automation (`run_sync`) executes in a background thread via
`loop.run_in_executor`. The thread and the event loop hand off the captcha
screenshot and the user's typed code through two `asyncio.Queue` objects
(`captcha_queue`, `code_queue`), bridged across the thread boundary with
`asyncio.run_coroutine_threadsafe`.

Both sides share one timeout constant, `CAPTCHA_TIMEOUT = 300`. This
symmetry matters: earlier, the thread side had a timeout but the event-loop
side didn't, so if the thread gave up waiting for a code, the event loop
would still wait forever for a Telegram reply that would never arrive —
a permanent, silent deadlock on that chat. If you touch this function, keep
both sides bounded by the same timeout.

## Known fragility: HTML parsing

`RutrackerClient._parse_search_results` parses rutracker's search results
table by CSS class name (`tor-tbl`, `t-title-col`, `tor-size`, etc.). When
rutracker renames these classes, the parser doesn't raise an error — it
silently returns zero results, which looks identical to "nothing found" from
the user's side. If search results ever go inexplicably empty, compare the
selectors in `_parse_search_results` against a live response body first
(temporarily logging `resp.text` from `RutrackerClient.search` to a file is
the fastest way to see the real markup).

## VDS constraints

Production runs on a 1 vCPU / ~1GB RAM VDS with a 2GB swap file. Headless
Chromium is heavy relative to that box: expect a fresh login (whenever the
rutracker session expires) to take 10-30 seconds, and don't be surprised if
unrelated work (e.g. Telegram API calls) briefly slows down while Chromium is
launching. That's a resource constraint, not a bug to chase.

## Deployment

See `README.md` for full setup instructions. Short version: pushing to
`main` on GitHub triggers a GitHub Actions workflow
(`.github/workflows/deploy.yml`) that SSHes into the VDS, runs `git pull`,
and restarts the `rutracker-bot` systemd service. `/opt/rutracker-bot` on the
VDS is a real git clone of this repo; the `.env` file there holds the actual
credentials and is never touched by a deploy.
