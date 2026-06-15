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

## Setup

### Requirements

- Python 3.10+
- Raspberry Pi (or any Linux server)
- Telegram Bot Token from [@BotFather](https://t.me/botfather)
- football-data.org API key (free tier)

### Install

```bash
git clone https://github.com/bibigon14/wc2026-telegram-bot.git
cd wc2026-telegram-bot
pip install requests schedule
```

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

### Run

```bash
python3 wc2026_bot.py
```

### Run as systemd service

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
