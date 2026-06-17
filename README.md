# ⚽ FIFA World Cup 2026 Telegram Bot

A real-time Telegram bot for the FIFA World Cup 2026, running on Raspberry Pi 5.

## Features

- 📅 Today's match schedule with kickoff times
- 🔴 Live scores and goal notifications
- 🏁 Final results as soon as the whistle blows
- ⏰ Match reminders 30 minutes before kickoff
- ☀️ Morning digest with the day's matches
- 🥅 Goals feed for today's matches
- 📊 Group standings
- 🏆 Top scorers with assists
- 🟨 Yellow and red card tracking
- 🗺️ Per-user timezone (`/timezone moscow`, `/timezone minsk`, etc.)
- 🌐 English / Russian localization (`/localization ru`)
- 👥 Multi-user subscriptions for auto-notifications
- ⚡ Redis-cached API calls — 10 min TTL, so a hundred people hitting `/standings` only costs one upstream request
- 🐳 Dockerized — runs in an isolated container with `restart: always`
- 🚦 Per-user rate limiting (5 commands/min) — keeps the bot polite to the upstream API when friends get spam-happy

## Commands

| Command | Description |
|---|---|
| `/today` | Today's matches |
| `/live` | Live scores right now |
| `/schedule Germany` | Full schedule for a team |
| `/next Brazil` | Next match for a team |
| `/standings Spain` | Group table |
| `/scorers` | Top scorers of the tournament |
| `/goals` | Goals scored today |
| `/groups` | All group standings |
| `/red` | Red cards in the tournament |
| `/yellow` | Yellow cards in the tournament |
| `/team USA` | Team overview |
| `/teams` | All 48 team names |
| `/bracket` | Knockout bracket |
| `/subscribe` | Subscribe to auto-notifications |
| `/unsubscribe` | Unsubscribe |
| `/timezone moscow` | Set your timezone |
| `/localization ru` | Switch language (en/ru) |

## Data Sources

- [ESPN API](https://site.api.espn.com) — live scores, goals, key events
- [football-data.org](https://football-data.org) — standings
- [openfootball](https://github.com/openfootball/world-cup) — match schedule

## Architecture

```
Telegram ⇄ wc2026_bot.py ⇄ Redis (cache + rate limit)
                  │
                  └──► football-data.org / ESPN / openfootball
```

Redis sits in front of every `football_api()` call with a 10-minute TTL, and
tracks a per-`chat_id` sliding window (5 requests/min) so no single user can
exhaust the bot's API quota. If Redis is ever unreachable, both the cache and
the rate limiter fail open — the bot keeps working exactly as if Redis didn't
exist, just without the caching benefit.

## Setup

### Requirements

- Docker + Docker Compose (recommended), or Python 3.10+ for a bare-metal run
- Telegram Bot Token from [@BotFather](https://t.me/botfather)
- football-data.org API key (free tier)

### Configure

Create `.env` file:

```env
BOT_TOKEN=your_telegram_bot_token
CHAT_ID=your_chat_id
FOOTBALL_API_KEY=your_football_data_api_key
SEND_TIME=08:00
CHECK_INTERVAL=5
LANG_BOT=en
```

### Run with Docker (recommended)

```bash
git clone https://github.com/bibigon14/wc2026-telegram-bot.git
cd wc2026-telegram-bot
docker compose up --build -d
docker compose logs -f wc2026bot
```

This starts two containers: `redis` (cache + rate limiting) and `wc2026bot`
(the bot itself), wired together on an internal Docker network. State files
(`subscribers.json`, `sent_results.json`, etc.) are bind-mounted from the
host, so they persist across rebuilds.

Check the cache is working:

```bash
docker exec -it homelab-redis redis-cli KEYS "wc2026:*"
```

### Run bare-metal (alternative)

```bash
git clone https://github.com/bibigon14/wc2026-telegram-bot.git
cd wc2026-telegram-bot
pip install -r requirements.txt
python3 wc2026_bot.py
```

Without a running Redis instance the bot falls back to no-cache, no-rate-limit
mode automatically — no extra configuration needed for a quick local test.

### Run as systemd service (bare-metal only)

```ini
[Unit]
Description=World Cup 2026 Telegram Bot
After=network.target

[Service]
User=your_user
WorkingDirectory=/path/to/wc2026-telegram-bot
EnvironmentFile=/path/to/wc2026-telegram-bot/.env
ExecStart=/usr/bin/python3 /path/to/wc2026-telegram-bot/wc2026_bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Privacy

The bot logs the following per command: timestamp, chat ID, Telegram username, language code. No personal data is shared or transmitted externally. Logs are stored locally on the server.

## License

MIT
