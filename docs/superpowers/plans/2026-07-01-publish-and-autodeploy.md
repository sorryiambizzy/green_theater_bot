# Publish to GitHub + Autodeploy + CLAUDE.md Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish this repo as a public GitHub project (`green_theater_bot`, MIT), add a `CLAUDE.md` for future sessions, and wire up autodeploy so pushes to `main` update the running bot on the VDS automatically.

**Architecture:** Local repo → pushed via personal SSH identity to a new public GitHub repo → VDS's `/opt/rutracker-bot` becomes a real `git clone` of that repo → GitHub Actions workflow SSHes into the VDS on every push to `main` and runs `git pull` + restart.

**Tech Stack:** git, GitHub CLI (`gh`), GitHub Actions (`appleboy/ssh-action`), systemd (existing).

## Global Constraints

- Git identity for this repo (already set locally, non-global): `user.email = podkine@mail.ru`. Never commit under `epodkin@naumen.ru` in this repo.
- Push over SSH using the existing personal key: `~/.ssh/id_ed25519_github_personal` (already aliased for `github.com` in `~/.ssh/config`, fingerprint `SHA256:bgUywNQz1FWBocbv5B9bZ98MXiIfoUzhi61yiMEx5qw`). Don't create or reference any other key.
- Repo name: `green_theater_bot`, visibility: public, license: MIT.
- No secrets (rutracker credentials, Telegram token, VDS root password, VDS IP is fine but no password) may appear in any committed file. `.env` stays gitignored.
- VDS: $VDS_HOST, root via password (existing), `/opt/rutracker-bot`, systemd unit `rutracker-bot.service`, 1 vCPU / ~1GB RAM + 2GB swap.
- Deploy target branch: `main` (rename local `master` → `main` as part of this work, since GitHub's default and the spec both assume `main`).

---

### Task 1: Authenticate `gh` CLI under the personal GitHub account

This is a one-time manual step — `gh auth login` requires an interactive browser/device-code flow that only the user can complete.

**Files:** none.

- [ ] **Step 1: Run in a terminal (not through an automated tool)**

```bash
gh auth login
```

Choose: `GitHub.com` → `HTTPS` (auth transport for the `gh` API calls; this is separate from the SSH key used for `git push`, which is already configured) → login via browser. Confirm the account is the **personal** one this project should live under (matching `podkine@mail.ru` / the personal SSH key), not any work account.

- [ ] **Step 2: Verify and record the GitHub username**

```bash
gh auth status
gh api user --jq .login
```

Expected: `gh auth status` shows "Logged in to github.com account <username>". Write down `<username>` — it's used as a literal substitution in Task 5 and the README.

---

### Task 2: Write CLAUDE.md

**Files:**
- Create: `CLAUDE.md`

**Interfaces:** none (documentation only).

- [ ] **Step 1: Write the file**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md"
```

---

### Task 3: Write README.md and LICENSE

**Files:**
- Create: `README.md`
- Create: `LICENSE`

**Interfaces:** none (documentation only). README references the GitHub username discovered in Task 1 — substitute it literally wherever `<username>` appears below.

- [ ] **Step 1: Write README.md**

```markdown
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
git clone git@github.com:<username>/green_theater_bot.git
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
git clone https://github.com/<username>/green_theater_bot.git /opt/rutracker-bot
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
```

- [ ] **Step 2: Write LICENSE**

```
MIT License

Copyright (c) 2026 Евгений Подкин

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Commit**

```bash
git add README.md LICENSE
git commit -m "docs: add README and MIT license"
```

---

### Task 4: Rename branch to `main`, create the GitHub repo, and push

**Files:** none created/modified — git operations only.

**Interfaces:**
- Consumes: `<username>` from Task 1.

- [ ] **Step 1: Rename the local branch**

```bash
git branch -m master main
```

- [ ] **Step 2: Create the GitHub repo without an automatic remote/push**

```bash
gh repo create green_theater_bot --public --description "Telegram bot for searching and downloading torrents from rutracker.org"
```

Expected output includes the new repo URL, e.g. `https://github.com/<username>/green_theater_bot`.

- [ ] **Step 3: Add the SSH remote explicitly (uses the personal key already configured for github.com) and push**

```bash
git remote add origin git@github.com:<username>/green_theater_bot.git
git push -u origin main
```

Expected: push succeeds, all 14 commits transferred, no prompt for a password (SSH key auth via `~/.ssh/config`'s `github.com` entry handles it).

- [ ] **Step 4: Verify on GitHub**

```bash
gh repo view --web
```

Confirm the browser opens the repo, shows the pushed commit history under the `podkine@mail.ru` identity (check a commit's author), and the README renders.

---

### Task 5: Convert `/opt/rutracker-bot` on the VDS into a real git clone

The server currently has loose files (copied via `scp`), not a git checkout. This task replaces it with a clone, without losing the live `.env`.

**Files (on the VDS, not local repo):**
- Replace: `/opt/rutracker-bot` (becomes a git clone)
- Preserve: `/opt/rutracker-bot/.env`

**Interfaces:**
- Consumes: `<username>` from Task 1, public repo from Task 4.

- [ ] **Step 1: Back up the live `.env` and stop the service**

```bash
ssh root@$VDS_HOST "cp /opt/rutracker-bot/.env /root/rutracker-bot.env.bak && systemctl stop rutracker-bot"
```

- [ ] **Step 2: Move the old directory aside and clone fresh (public repo, HTTPS, no auth needed)**

```bash
ssh root@$VDS_HOST "mv /opt/rutracker-bot /opt/rutracker-bot.old && git clone https://github.com/<username>/green_theater_bot.git /opt/rutracker-bot"
```

- [ ] **Step 3: Restore `.env`, recreate the venv, reinstall dependencies + Playwright browser**

```bash
ssh root@$VDS_HOST "cp /root/rutracker-bot.env.bak /opt/rutracker-bot/.env && cd /opt/rutracker-bot && python3 -m venv venv && venv/bin/pip install -r requirements.txt && venv/bin/playwright install --with-deps chromium"
```

- [ ] **Step 4: Start the service and verify**

```bash
ssh root@$VDS_HOST "systemctl start rutracker-bot && sleep 2 && systemctl is-active rutracker-bot"
```

Expected: `active`.

```bash
ssh root@$VDS_HOST "cd /opt/rutracker-bot && git status --short && git log -1 --oneline"
```

Expected: clean working tree, latest commit matches `git log -1` from the local repo.

- [ ] **Step 5: Remove the old directory once confirmed working**

```bash
ssh root@$VDS_HOST "rm -rf /opt/rutracker-bot.old /root/rutracker-bot.env.bak"
```

---

### Task 6: Add the GitHub Actions autodeploy workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: GitHub secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PASSWORD` (set in Step 1 below).

- [ ] **Step 1: Set the GitHub Actions secrets (uses `gh` auth from Task 1)**

Run these interactively in a terminal — do not write the password into any file, plan, or command that gets logged/committed. `gh secret set NAME` with no `--body` prompts you to type the value, which is never echoed or saved anywhere:

```bash
gh secret set DEPLOY_HOST    # paste: $VDS_HOST
gh secret set DEPLOY_USER    # paste: root
gh secret set DEPLOY_PASSWORD    # paste the VDS root password
```

Expected: each command prints `Set Secret DEPLOY_HOST for <username>/green_theater_bot` (etc.).

- [ ] **Step 2: Write the workflow file**

```yaml
name: Deploy to VDS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          password: ${{ secrets.DEPLOY_PASSWORD }}
          script: |
            cd /opt/rutracker-bot
            git fetch origin main
            git reset --hard origin/main
            venv/bin/pip install -r requirements.txt
            systemctl restart rutracker-bot
```

- [ ] **Step 3: Commit and push**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: add autodeploy workflow on push to main"
git push origin main
```

This push itself triggers the first real run of the workflow — proceed straight to Task 7 to watch it.

---

### Task 7: End-to-end verification

**Files:** none.

- [ ] **Step 1: Watch the triggered Actions run**

```bash
gh run watch
```

Expected: the run started by Task 6's push completes with a green checkmark. If it fails, `gh run view --log-failed` shows which SSH step failed.

- [ ] **Step 2: Confirm the VDS actually updated**

```bash
ssh root@$VDS_HOST "cd /opt/rutracker-bot && git log -1 --oneline && systemctl status rutracker-bot --no-pager | head -5"
```

Expected: latest commit matches what's on GitHub's `main`, service shows a recent "Active: active (running)" with a start time matching when the workflow ran.

- [ ] **Step 3: Smoke-test the bot**

Send any search query to the bot in Telegram. Expected: normal search results come back (confirms the restart didn't break anything and `.env` survived the directory swap in Task 5).

- [ ] **Step 4: Make a trivial follow-up change to confirm the loop is real**

Edit `README.md` (add a blank line, or similar trivial change), commit, push to `main`, and repeat Steps 1-2 to confirm a *second* autodeploy also works end-to-end.
