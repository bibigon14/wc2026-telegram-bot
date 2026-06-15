#!/usr/bin/env python3
"""
Telegram bot — FIFA World Cup 2026

Auto features:
  📅 Daily schedule every morning at SEND_TIME
  🏁 Match result as soon as it finishes
  ⏰ Reminder 30 min before each match
  📊 Live score update when a goal is scored

Commands:
  /today          — today's matches
  /schedule <team>— group stage schedule for a team
  /next <team>    — next match + countdown
  /standings <team> — group table
  /live           — live scores right now

Setup:
  pip3 install requests schedule --break-system-packages
  1. Fill in BOT_TOKEN, CHAT_ID, FOOTBALL_API_KEY below
  2. python3 wc2026_bot.py
"""

import json
import os
import re
import sys
import time
import threading
import requests
import schedule
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

BOT_TOKEN        = os.environ["BOT_TOKEN"]
CHAT_ID          = os.environ["CHAT_ID"]
FOOTBALL_API_KEY = os.environ["FOOTBALL_API_KEY"]
SEND_TIME        = os.getenv("SEND_TIME", "08:00")  # daily schedule, Pacific Time
LANG_BOT         = os.getenv("LANG_BOT", "en")        # "en" or "ru"
_user_ctx        = threading.local()

SCHEDULE_URL  = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
API_BASE      = "https://api.football-data.org/v4"
API_HEADERS   = {"X-Auth-Token": FOOTBALL_API_KEY}
ESPN_URL      = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

LOCAL_TZ = timezone(timedelta(hours=-7))  # PDT; change to -8 in winter
TZ_ALIASES = {
    "pt": "America/Los_Angeles", "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles",
    "pacific": "America/Los_Angeles", "la": "America/Los_Angeles", "california": "America/Los_Angeles",
    "et": "America/New_York", "est": "America/New_York", "eastern": "America/New_York", "ny": "America/New_York",
    "ct": "America/Chicago", "cst": "America/Chicago", "chicago": "America/Chicago",
    "mt": "America/Denver", "mst": "America/Denver", "denver": "America/Denver",
    "utc": "UTC", "gmt": "UTC",
    "london": "Europe/London", "uk": "Europe/London",
    "moscow": "Europe/Moscow", "msk": "Europe/Moscow", "russia": "Europe/Moscow",
    "dubai": "Asia/Dubai", "uae": "Asia/Dubai",
    "seoul": "Asia/Seoul", "korea": "Asia/Seoul",
    "tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo",
    "beijing": "Asia/Shanghai", "china": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "paris": "Europe/Paris", "france": "Europe/Paris",
    "berlin": "Europe/Berlin", "amsterdam": "Europe/Amsterdam",
    "istanbul": "Europe/Istanbul",
    "kyiv": "Europe/Kyiv", "kiev": "Europe/Kyiv", "ukraine": "Europe/Kyiv", "ua": "Europe/Kyiv",
    "minsk": "Europe/Minsk", "belarus": "Europe/Minsk", "by": "Europe/Minsk",
    "toronto": "America/Toronto", "mexico": "America/Mexico_City",
    "argentina": "America/Argentina/Buenos_Aires", "brazil": "America/Sao_Paulo",
}

def get_user_tz(chat_id: str):
    tzs = load_json(TIMEZONES_FILE) or {}
    name = tzs.get(str(chat_id))
    if name:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    return LOCAL_TZ

def set_user_tz(chat_id: str, tz_name: str) -> bool:
    try:
        ZoneInfo(tz_name)
        tzs = load_json(TIMEZONES_FILE) or {}
        tzs[str(chat_id)] = tz_name
        save_json(TIMEZONES_FILE, tzs)
        return True
    except Exception:
        return False

def get_user_lang(chat_id: str) -> str:
    langs = load_json(LANG_FILE) or {}
    return langs.get(str(chat_id), LANG_BOT)

def set_user_lang(chat_id: str, lang: str):
    langs = load_json(LANG_FILE) or {}
    langs[str(chat_id)] = lang
    save_json(LANG_FILE, langs)

def tz_label(tz) -> str:
    _friendly = {
        "Europe/Minsk":  "FET",
        "Europe/Moscow": "MSK",
        "Europe/Kyiv":   "EET",
        "Europe/Kiev":   "EET",
        "Asia/Dubai":    "GST",
        "Asia/Kolkata":  "IST",
    }
    if hasattr(tz, 'key') and tz.key in _friendly:
        return _friendly[tz.key]
    abbr = datetime.now(tz).strftime("%Z")
    # Replace ugly +XX with offset string
    if abbr.startswith("+") or abbr.startswith("-"):
        return "UTC" + abbr
    return abbr



STATE_DIR          = os.path.dirname(os.path.abspath(__file__))
SENT_RESULTS_FILE  = os.path.join(STATE_DIR, "sent_results.json")
SENT_REMINDERS_FILE= os.path.join(STATE_DIR, "sent_reminders.json")
LIVE_SCORES_FILE   = os.path.join(STATE_DIR, "live_scores.json")
SUBSCRIBERS_FILE   = os.path.join(STATE_DIR, "subscribers.json")
TIMEZONES_FILE     = os.path.join(STATE_DIR, "timezones.json")
LANG_FILE          = os.path.join(STATE_DIR, "user_langs.json")

FLAG = {
    "Mexico": "🇲🇽", "South Africa": "🇿🇦", "South Korea": "🇰🇷",
    "Canada": "🇨🇦", "Qatar": "🇶🇦", "Switzerland": "🇨🇭",
    "Brazil": "🇧🇷", "Morocco": "🇲🇦", "Haiti": "🇭🇹", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "USA": "🇺🇸", "Paraguay": "🇵🇾", "Australia": "🇦🇺",
    "Germany": "🇩🇪", "Curaçao": "🇨🇼", "Ivory Coast": "🇨🇮", "Côte d'Ivoire": "🇨🇮", "Cote d'Ivoire": "🇨🇮", "Ecuador": "🇪🇨",
    "Netherlands": "🇳🇱", "Japan": "🇯🇵", "Tunisia": "🇹🇳",
    "Belgium": "🇧🇪", "Egypt": "🇪🇬", "Iran": "🇮🇷", "New Zealand": "🇳🇿",
    "Spain": "🇪🇸", "Cape Verde": "🇨🇻", "Saudi Arabia": "🇸🇦", "Uruguay": "🇺🇾",
    "France": "🇫🇷", "Senegal": "🇸🇳", "Norway": "🇳🇴",
    "Argentina": "🇦🇷", "Algeria": "🇩🇿", "Austria": "🇦🇹", "Jordan": "🇯🇴",
    "Portugal": "🇵🇹", "Uzbekistan": "🇺🇿", "Colombia": "🇨🇴",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Croatia": "🇭🇷", "Ghana": "🇬🇭", "Panama": "🇵🇦",
    "United States": "🇺🇸", "Bosnia & Herzegovina": "🇧🇦", "Bosnia-Herzegovina": "🇧🇦", "Bosnia and Herzegovina": "🇧🇦", "Korea Republic": "🇰🇷",
    "Czechia": "🇨🇿", "Czech Republic": "🇨🇿", "Turkey": "🇹🇷",
    "Türkiye": "🇹🇷", "Serbia": "🇷🇸", "Romania": "🇷🇴", "Ukraine": "🇺🇦",
    "Hungary": "🇭🇺", "Slovakia": "🇸🇰", "Greece": "🇬🇷", "Albania": "🇦🇱",
    "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Northern Ireland": "🇬🇧", "Ireland": "🇮🇪",
    "Denmark": "🇩🇰", "Sweden": "🇸🇪", "Finland": "🇫🇮",
    "Iceland": "🇮🇸", "Kosovo": "🇽🇰",
    "Cameroon": "🇨🇲", "Nigeria": "🇳🇬", "Senegal": "🇸🇳",
    "Mali": "🇲🇱", "Ivory Coast": "🇨🇮", "Côte d'Ivoire": "🇨🇮", "Cote d'Ivoire": "🇨🇮", "Ghana": "🇬🇭",
    "DR Congo": "🇨🇩", "Angola": "🇦🇴",
    "Japan": "🇯🇵", "South Korea": "🇰🇷", "Iran": "🇮🇷",
    "Iraq": "🇮🇶", "Uzbekistan": "🇺🇿", "Jordan": "🇯🇴",
    "Mexico": "🇲🇽", "USA": "🇺🇸", "Canada": "🇨🇦",
    "Costa Rica": "🇨🇷", "Honduras": "🇭🇳", "Panama": "🇵🇦",
    "Jamaica": "🇯🇲", "Trinidad and Tobago": "🇹🇹",
    "Argentina": "🇦🇷", "Brazil": "🇧🇷", "Colombia": "🇨🇴",
    "Uruguay": "🇺🇾", "Ecuador": "🇪🇨", "Venezuela": "🇻🇪",
    "Chile": "🇨🇱", "Bolivia": "🇧🇴", "Peru": "🇵🇪",
    "Australia": "🇦🇺", "New Zealand": "🇳🇿",
}



# ── Translations ──────────────────────────

T = {
    "en": {
        "schedule_header": "⚽ *World Cup 2026 — {date}*",
        "no_matches":      "⚽ *World Cup 2026 | {date}*\n\nNo matches today 🏖",
        "enjoy":           "_Enjoy the games!_ 🏆",
        "full_time":       "🏁 Full time",
        "pens":            " (pens)",
        "aet":             " (a.e.t.)",
        "kickoff_30":      "⏰ Kickoff in 30 min! | {stage}",
        "kickoff_time":    "🕐 {time} {tz}  📍 {city}",
        "goal":            "⚽ Goal! {minute}'",
        "live_header":     "🔴 *Live now*",
        "no_live":         "⚽ No matches live right now.",
        "usage_schedule":  "Usage: /schedule Argentina  (see /teams for names)",
        "usage_next":      "Usage: /next Argentina  (see /teams for names)",
        "usage_standings": "Usage: /standings Germany  (see /teams for names)",
        "usage_team":      "Usage: /team Germany  (see /teams for names)",
        "team_not_found":  "❌ Team not found: {query}",
        "no_group":        "No group stage matches found for *{team}*.",
        "no_upcoming":     "No upcoming matches for *{team}*.",
        "next_match":      "⏭ *Next match: {team}*",
        "in":              "In",
        "standings_na":    "❌ Team not found or standings not available yet for *{query}*.",
        "standings_na2":   "Standings not available yet.",
        "standings_hdr":   "📊 *Standings — {group}*",
        "scorers_hdr":     "⚽ *Top Scorers — World Cup 2026*",
        "no_scorers":      "No goals scored yet.",
        "no_finished":     "No finished matches yet.",
        "groups_hdr":      "🏆 *World Cup 2026 — Standings*",
        "goals_hdr":       "⚽ *Goals Today — World Cup 2026*",
        "no_goals":        "No goals scored today yet.",
        "red_hdr":         "🟥 *Red Cards — World Cup 2026*",
        "no_red":          "🟥 No red cards in the tournament yet.",
        "yellow_hdr":      "🟨 *Yellow Cards — Top Teams*",
        "no_yellow":       "🟨 No yellow cards yet.",
        "recent":          "📋 *Recent results:*",
        "yellow_n":        "🟨 *Yellow cards ({n}):*",
        "next_vs":         "⏭ *Next:* vs {opp}",
        "bracket_hdr":     "🏆 *World Cup 2026 — Knockout Stage*",
        "bracket_wait":    "⏳ Knockout stage hasn\'t started yet.\nGroup stage runs until June 27.",
        "d": "d", "h": "h", "m": "m",
        "cmd_today":     "Today\'s matches",
        "cmd_schedule":  "Team group schedule — /schedule Germany",
        "cmd_next":      "Next match for a team — /next Brazil",
        "cmd_standings": "Group table — /standings Spain",
        "cmd_live":      "Live scores right now",
        "cmd_scorers":   "Top scorers of the tournament",
        "cmd_groups":    "All group standings",
        "cmd_goals":     "Goals scored today",
        "cmd_red":       "Red cards in the tournament",
        "cmd_yellow":    "Yellow cards in the tournament",
        "cmd_team":      "Team overview — /team USA",
        "cmd_bracket":   "Knockout stage bracket",
        "cmd_teams":     "All team names for bot commands",
        "cmd_subscribe":  "Subscribe to auto-notifications",
        "cmd_timezone":   "Set your timezone — /timezone moscow",
        "cmd_localization": "Switch language — /localization ru",
        "cmd_unsubscribe": "Unsubscribe from notifications",
        "subscribed":     "Subscribed! You will receive auto-notifications.",
        "already_sub":    "You are already subscribed.",
        "unsubscribed":   "Unsubscribed.",
        "not_sub":        "You are not subscribed.",
        "teams_hdr":     "📋 *WC 2026 — All Teams*",
        "teams_hint":    "Use these names with /schedule /next /standings /team",
    },
    "ru": {
        "schedule_header": "⚽ *ЧМ 2026 — {date}*",
        "no_matches":      "⚽ *ЧМ 2026 | {date}*\n\nСегодня матчей нет 🏖",
        "enjoy":           "_Приятного просмотра!_ 🏆",
        "full_time":       "🏁 Финальный свисток",
        "pens":            " (пен.)",
        "aet":             " (д.в.)",
        "kickoff_30":      "⏰ Начало через 30 минут! | {stage}",
        "kickoff_time":    "🕐 {time} {tz}  📍 {city}",
        "goal":            "⚽ Гол! {minute}'",
        "live_header":     "🔴 *Сейчас в эфире*",
        "no_live":         "⚽ Матчей в прямом эфире нет.",
        "usage_schedule":  "Использование: /schedule Argentina (названия из /teams)",
        "usage_next":      "Использование: /next Argentina (названия из /teams)",
        "usage_standings": "Использование: /standings Germany (названия из /teams)",
        "usage_team":      "Использование: /team Germany (названия из /teams)",
        "team_not_found":  "❌ Команда не найдена: {query}",
        "no_group":        "Матчей группового этапа для *{team}* не найдено.",
        "no_upcoming":     "Предстоящих матчей для *{team}* нет.",
        "next_match":      "⏭ *Следующий матч: {team}*",
        "in":              "Через",
        "standings_na":    "❌ Команда не найдена или таблица недоступна для *{query}*.",
        "standings_na2":   "Таблица ещё недоступна.",
        "standings_hdr":   "📊 *Таблица — {group}*",
        "scorers_hdr":     "⚽ *Бомбардиры — ЧМ 2026*",
        "no_scorers":      "Голов пока не забито.",
        "no_finished":     "Завершённых матчей пока нет.",
        "groups_hdr":      "🏆 *ЧМ 2026 — Таблицы групп*",
        "goals_hdr":       "⚽ *Голы сегодня — ЧМ 2026*",
        "no_goals":        "Сегодня голов пока нет.",
        "red_hdr":         "🟥 *Красные карточки — ЧМ 2026*",
        "no_red":          "🟥 Красных карточек пока нет.",
        "yellow_hdr":      "🟨 *Жёлтые карточки — Топ команд*",
        "no_yellow":       "🟨 Жёлтых карточек пока нет.",
        "recent":          "📋 *Последние результаты:*",
        "yellow_n":        "🟨 *Жёлтые карточки ({n}):*",
        "next_vs":         "⏭ *Следующий:* vs {opp}",
        "bracket_hdr":     "🏆 *ЧМ 2026 — Плей-офф*",
        "bracket_wait":    "⏳ Плей-офф ещё не начался.\nГрупповой этап идёт до 27 июня.",
        "d": "д", "h": "ч", "m": "м",
        "cmd_today":     "Матчи сегодня",
        "cmd_schedule":  "Расписание команды — /schedule Germany",
        "cmd_next":      "Следующий матч — /next Brazil",
        "cmd_standings": "Таблица группы — /standings Spain",
        "cmd_live":      "Прямой эфир",
        "cmd_scorers":   "Бомбардиры турнира",
        "cmd_groups":    "Все групповые таблицы",
        "cmd_goals":     "Голы сегодня",
        "cmd_red":       "Красные карточки",
        "cmd_yellow":    "Жёлтые карточки",
        "cmd_team":      "Обзор команды — /team USA",
        "cmd_bracket":   "Сетка плей-офф",
        "cmd_teams":     "Все команды для команд бота",
        "cmd_subscribe":  "Подписаться на авто-уведомления",
        "cmd_timezone":   "Установить часовой пояс — /timezone moscow",
        "cmd_localization": "Язык бота — /localization en",
        "cmd_unsubscribe": "Отписаться от уведомлений",
        "subscribed":     "Подписан! Будешь получать авто-уведомления.",
        "already_sub":    "Ты уже подписан.",
        "unsubscribed":   "Отписан.",
        "not_sub":        "Ты не подписан.",
        "teams_hdr":     "📋 *ЧМ 2026 — Все команды*",
        "teams_hint":    "Используй с /schedule /next /standings /team",
    }
}

def t(key: str, **kwargs) -> str:
    lang = getattr(_user_ctx, 'lang', LANG_BOT)
    s = T.get(lang, T["en"]).get(key, T["en"].get(key, key))
    return s.format(**kwargs) if kwargs else s


# ── Helpers ───────────────────────────────

def flag(name: str) -> str:
    return FLAG.get(name, "🏳️")

def team_str(name: str) -> str:
    return f"{flag(name)} {name}"

def to_local_dt(date_str: str, time_str: str, tz=None) -> datetime:
    tz = tz if tz is not None else LOCAL_TZ
    m = re.match(r"(\d+):(\d+)\s+UTC([+-]\d+)", time_str)
    if not m:
        return datetime.min.replace(tzinfo=tz)
    h, mi, off = int(m.group(1)), int(m.group(2)), int(m.group(3))
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(
        hour=h, minute=mi, tzinfo=timezone(timedelta(hours=off))
    )
    return dt.astimezone(tz)

def to_local(date_str: str, time_str: str, tz=None) -> str:
    return to_local_dt(date_str, time_str, tz).strftime("%I:%M %p")

def now_pt() -> datetime:
    return datetime.now(LOCAL_TZ)

def load_json(path: str) -> dict | list:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def save_json(path: str, data):
    with open(path, "w") as f:
        json.dump(data, f)

def fetch_openfootball() -> list:
    """Parse openfootball txt schedule (new format)."""
    try:
        url = "https://raw.githubusercontent.com/openfootball/worldcup/master/2026--usa/cup.txt"
        text = requests.get(url, timeout=15).text
        MONTHS = {
            "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
            "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
            "january":1,"february":2,"march":3,"april":4,"june":6,
            "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
        }
        matches = []
        current_date = None
        current_group = ""
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("=") or s.startswith("("):
                continue
            # Group header: ▪ Group A
            gm = re.match(r"[^\w]*Group\s+(\S+)", s)
            if gm and "Matchday" not in s:
                current_group = f"Group {gm.group(1)}"
                continue
            # Date header: Thu June 11 or Mon Jun 15
            dm = re.match(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\w+)\s+(\d+)", s)
            if dm:
                mn = MONTHS.get(dm.group(1).lower()) or MONTHS.get(dm.group(1).lower()[:3])
                if mn:
                    current_date = f"2026-{mn:02d}-{int(dm.group(2)):02d}"
                continue
            # Match line: 13:00 UTC-6   Team1  v  Team2  @ City
            mm = re.match(r"(\d{2}:\d{2})\s+UTC([+-]\d+)\s+(.+)", s)
            if mm and current_date:
                h, mi = map(int, mm.group(1).split(":"))
                off = int(mm.group(2))
                sign = "+" if off >= 0 else ""
                utc_t = f"{h:02d}:{mi:02d} UTC{sign}{off}"
                rest = mm.group(3)
                at = rest.rsplit("@", 1)
                if len(at) != 2:
                    continue
                body = at[0].strip()
                venue = at[1].strip()
                # Scheduled: "Team1   v   Team2"
                vm = re.match(r"(.+?)\s{2,}v\s+(.+)", body)
                if vm:
                    t1, t2 = vm.group(1).strip(), vm.group(2).strip()
                else:
                    # Finished: "Team1   2-1 (1-0)   Team2"
                    fm = re.match(r"(.+?)\s{2,}\d+-\d+(?:\s*\([^)]+\))?\s+(.+)", body)
                    if fm:
                        t1, t2 = fm.group(1).strip(), fm.group(2).strip()
                    else:
                        continue
                matches.append({
                    "date": current_date, "time": utc_t,
                    "team1": t1, "team2": t2,
                    "ground": venue, "group": current_group, "round": "",
                })
        return matches
    except Exception as e:
        print(f"[fetch_openfootball] ERR: {e}")
        return []

def football_api(endpoint: str, params: dict = None):
    r = requests.get(f"{API_BASE}{endpoint}", headers=API_HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def find_team(query: str, matches: list) -> str | None:
    query = query.strip().lower()
    teams = set()
    for m in matches:
        teams.add(m["team1"])
        teams.add(m["team2"])
    for team in sorted(teams):
        if query in team.lower():
            return team
    return None


# ── Telegram send ─────────────────────────

def send_md(text: str, chat_id: str = None):
    """Send with Markdown formatting."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id or CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }, timeout=15)

def send_plain(text: str, chat_id: str = None):
    """Send plain text, no formatting."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id or CHAT_ID,
        "text": text
    }, timeout=15)

def reply(chat_id: str, text: str):
    send_md(text, chat_id)


# ── Daily schedule ────────────────────────

def build_schedule_message(matches: list, date_str: str, tz=None) -> str:
    tz = tz if tz is not None else LOCAL_TZ
    tlabel = tz_label(tz)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    date_fmt = dt.strftime("%B %-d, %Y")

    if not matches:
        return t("no_matches", date=date_fmt)

    lines = [t("schedule_header", date=date_fmt) + "\n"]
    for m in sorted(matches, key=lambda m: to_local_dt(m["date"], m["time"])):
        pt    = to_local(m["date"], m["time"], tz)
        stage = m.get("group") or m.get("round", "")
        city  = m.get("ground", "")
        lines.append(f"🕐 *{pt} {tlabel}* — {team_str(m['team1'])} vs {team_str(m['team2'])}")
        lines.append(f"   📍 {city}  |  {stage}\n")
    lines.append(t("enjoy"))
    return "\n".join(lines)

def job_schedule():
    try:
        today = now_pt().strftime("%Y-%m-%d")
        all_m = fetch_openfootball()
        matches = [m for m in all_m if m["date"] == today]
        for _cid in load_subscribers():
            send_md(build_schedule_message(matches, today, get_user_tz(_cid)), _cid)
        print(f"[{now_pt().strftime('%I:%M %p PT')}] ✅ Schedule sent ({len(matches)} matches)")
    except Exception as e:
        print(f"[{now_pt().strftime('%I:%M %p PT')}] ❌ Schedule: {e}")


# ── Results ───────────────────────────────

def fetch_espn_events():
    """Return all events from ESPN scoreboard (today + tomorrow UTC to cover late PT matches)."""
    seen = set()
    events = []
    utc_now = datetime.now(timezone.utc)
    for delta in (-1, 0, 1):
        date_str = (utc_now + timedelta(days=delta)).strftime("%Y%m%d")
        r = requests.get(ESPN_URL, params={"dates": date_str}, timeout=15)
        r.raise_for_status()
        for e in r.json().get("events", []):
            if e["id"] not in seen:
                seen.add(e["id"])
                events.append(e)
    return events


def job_results():
    try:
        sent = set(load_json(SENT_RESULTS_FILE) or [])
        new  = False

        for event in fetch_espn_events():
            if event["status"]["type"]["name"] != "STATUS_FULL_TIME":
                continue
            eid  = event["id"]
            if eid in sent:
                continue
            comp = event["competitions"][0]
            # ESPN competitors: index 0 = home, index 1 = away
            home_c = next((c for c in comp["competitors"] if c["homeAway"] == "home"), comp["competitors"][0])
            away_c = next((c for c in comp["competitors"] if c["homeAway"] == "away"), comp["competitors"][1])
            home   = home_c["team"]["displayName"]
            away   = away_c["team"]["displayName"]
            h      = int(home_c.get("score") or 0)
            a      = int(away_c.get("score") or 0)
            # Check for extra time / penalties in notes
            extra  = ""
            notes  = comp.get("notes", [])
            if notes:
                txt = notes[0].get("text", "").lower()
                if "penalty" in txt or "shootout" in txt:
                    extra = t("pens")
                elif "extra" in txt or "aet" in txt:
                    extra = t("aet")
            group = event.get("season", {}).get("slug", "").replace("-", " ").title()
            broadcast_plain(f"{t('full_time')}\n{team_str(home)} {h}–{a} {team_str(away)}{extra}")
            sent.add(eid)
            new = True
            print(f"[{now_pt().strftime('%I:%M %p PT')}] 🏁 Result: {home} {h}–{a} {away}")
            time.sleep(1)

        if new:
            save_json(SENT_RESULTS_FILE, list(sent))
    except Exception as e:
        print(f"[{now_pt().strftime('%I:%M %p PT')}] ❌ Results: {e}")


# ── Reminders (30 min before) ─────────────

def job_reminders():
    try:
        sent = set(load_json(SENT_REMINDERS_FILE) or [])
        all_m = fetch_openfootball()
        now   = now_pt()
        new   = False

        for m in all_m:
            kick_off = to_local_dt(m["date"], m["time"])
            mins_to  = (kick_off - now).total_seconds() / 60
            uid      = f"{m['date']}_{m['team1']}_{m['team2']}"

            if 28 <= mins_to <= 32 and uid not in sent:
                stage = m.get("group") or m.get("round", "")
                city  = m.get("ground", "")
                pt    = to_local(m["date"], m["time"])
                broadcast_plain(
                    f"{t('kickoff_30', stage=stage)}\n"
                    f"{team_str(m['team1'])} vs {team_str(m['team2'])}\n" +
                    t("kickoff_time", time=pt, city=city)
                )
                sent.add(uid)
                new = True
                print(f"[{now_pt().strftime('%I:%M %p PT')}] ⏰ Reminder: {m['team1']} vs {m['team2']}")

        if new:
            save_json(SENT_REMINDERS_FILE, list(sent))
    except Exception as e:
        print(f"[{now_pt().strftime('%I:%M %p PT')}] ❌ Reminders: {e}")


# ── Live score updates ────────────────────

LIVE_STATUSES = {
    "STATUS_IN_PROGRESS", "STATUS_HALFTIME",
    "STATUS_FIRST_HALF", "STATUS_SECOND_HALF",
}

def job_live():
    try:
        prev    = load_json(LIVE_SCORES_FILE) or {}
        updated = dict(prev)

        for event in fetch_espn_events():
            status = event["status"]["type"]["name"]
            if status not in LIVE_STATUSES:
                continue
            eid  = event["id"]
            comp = event["competitions"][0]
            home_c = next((c for c in comp["competitors"] if c["homeAway"] == "home"), comp["competitors"][0])
            away_c = next((c for c in comp["competitors"] if c["homeAway"] == "away"), comp["competitors"][1])
            home   = home_c["team"]["displayName"]
            away   = away_c["team"]["displayName"]
            h      = int(home_c.get("score") or 0)
            a      = int(away_c.get("score") or 0)
            key    = f"{h}-{a}"
            minute = event["status"].get("displayClock", "?")

            if eid in prev and prev[eid] != key:
                broadcast_plain(
                    f"{t('goal', minute=minute)}\n"
                    f"{team_str(home)} {h}–{a} {team_str(away)}"
                )
                print(f"[{now_pt().strftime('%I:%M %p PT')}] ⚽ Goal: {home} {h}–{a} {away} ({minute}')")

            updated[eid] = key

        # Clean up finished matches from live state
        active_ids = {e["id"] for e in fetch_espn_events() if e["status"]["type"]["name"] in LIVE_STATUSES}
        for eid in list(updated.keys()):
            if eid not in active_ids:
                del updated[eid]

        save_json(LIVE_SCORES_FILE, updated)
    except Exception as e:
        print(f"[{now_pt().strftime('%I:%M %p PT')}] ❌ Live: {e}")


# ── Commands ──────────────────────────────

def cmd_today(chat_id: str):
    tz    = get_user_tz(chat_id)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    all_m = fetch_openfootball()
    matches = [m for m in all_m if m["date"] == today]
    reply(chat_id, build_schedule_message(matches, today, tz))


def cmd_schedule(chat_id: str, query: str):
    if not query:
        reply(chat_id, t("usage_schedule"))
        return
    all_m  = fetch_openfootball()
    team   = find_team(query, all_m)
    if not team:
        reply(chat_id, t("team_not_found", query=query))
        return
    group_m = [m for m in all_m if (m["team1"] == team or m["team2"] == team) and m.get("group")]
    if not group_m:
        reply(chat_id, t("no_group", team=team))
        return
    group = group_m[0].get("group", "")
    lines = [f"⚽ *{team_str(team)}* — {group}\n"]
    for m in sorted(group_m, key=lambda m: to_local_dt(m["date"], m["time"])):
        opp      = m["team2"] if m["team1"] == team else m["team1"]
        tz       = get_user_tz(chat_id)
        pt       = to_local(m["date"], m["time"], tz)
        date_fmt = datetime.strptime(m["date"], "%Y-%m-%d").strftime("%b %-d")
        home     = m["team1"] == team
        vs       = f"{team_str(team)} vs {team_str(opp)}" if home else f"{team_str(opp)} vs {team_str(team)}"
        lines.append(f"📅 *{date_fmt}* | 🕐 {pt} {tz_label(tz)}\n   {vs}\n   📍 {m.get('ground', '')}\n")
    reply(chat_id, "\n".join(lines))


def cmd_next(chat_id: str, query: str):
    if not query:
        reply(chat_id, t("usage_next"))
        return
    all_m = fetch_openfootball()
    team  = find_team(query, all_m)
    if not team:
        reply(chat_id, t("team_not_found", query=query))
        return
    now   = now_pt()
    upcoming = [
        m for m in all_m
        if (m["team1"] == team or m["team2"] == team)
        and to_local_dt(m["date"], m["time"]) > now
    ]
    if not upcoming:
        reply(chat_id, t("no_upcoming", team=team_str(team)))
        return
    m    = sorted(upcoming, key=lambda m: to_local_dt(m["date"], m["time"]))[0]
    kick = to_local_dt(m["date"], m["time"])
    diff = kick - now
    days = diff.days
    hours, rem = divmod(diff.seconds, 3600)
    mins  = rem // 60
    if days > 0:
        countdown = f"{days}d {hours}h {mins}m"
    elif hours > 0:
        countdown = f"{hours}h {mins}m"
    else:
        countdown = f"{mins}m"
    opp   = m["team2"] if m["team1"] == team else m["team1"]
    stage = m.get("group") or m.get("round", "")
    reply(chat_id,
        t("next_match", team=team_str(team)) + "\n\n"
        f"{team_str(m['team1'])} vs {team_str(m['team2'])}\n"
        f"📅 {kick.strftime('%b %-d')} | 🕐 {kick.strftime('%I:%M %p')} {tz_label(get_user_tz(chat_id))}\n"
        f"📍 {m.get('ground', '')}  |  {stage}\n"
        f"{t('in')} {countdown}"
    )


STANDINGS_ALIASES = {
    "usa": "united states",
    "us":  "united states",
    "usa": "united states",
    "korea": "korea republic",
    "south korea": "korea republic",
    "england": "england",
    "czechia": "czech",
    "ivory coast": "côte d'ivoire",
    "bosnia": "bosnia",
}

def cmd_standings(chat_id: str, query: str):
    if not query:
        reply(chat_id, t("usage_standings"))
        return
    all_m = fetch_openfootball()
    team  = find_team(query, all_m)

    data  = football_api("/competitions/WC/standings")
    # Normalise search terms: original query, alias, and openfootball name
    q = query.strip().lower()
    search_terms = {q, STANDINGS_ALIASES.get(q, q)}
    if team:
        search_terms.add(team.lower())

    target_group = None
    for standing in data.get("standings", []):
        for row in standing.get("table", []):
            api_name = row["team"]["name"].lower()
            if any(t in api_name or api_name in t for t in search_terms):
                target_group = standing
                break
        if target_group:
            break

    if not target_group:
        reply(chat_id, t("standings_na", query=query))
        return

    if not target_group:
        reply(chat_id, t("standings_na", query=team))
        return

    group_name = (target_group.get("group") or "").replace("_", " ").title()
    lines = [t("standings_hdr", group=group_name) + "\n"]
    lines.append("`#  Team                 P  W  D  L  GD Pts`")
    for row in target_group["table"]:
        pos  = row["position"]
        name = row["team"]["name"][:18]
        f_   = flag(row["team"]["name"])
        p    = row["playedGames"]
        w    = row["won"]
        d    = row["draw"]
        l    = row["lost"]
        gd   = row["goalDifference"]
        pts  = row["points"]
        gd_s = f"+{gd}" if gd > 0 else str(gd)
        lines.append(f"`{pos:<2} {f_} {name:<18} {p}  {w}  {d}  {l}  {gd_s:<3} {pts}`")

    reply(chat_id, "\n".join(lines))



def fetch_all_espn_events():
    """Fetch all WC events from tournament start to tomorrow UTC."""
    from datetime import date as date_
    seen   = set()
    events = []
    start  = date_(2026, 6, 11)
    end    = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    d = start
    while d <= end:
        r = requests.get(ESPN_URL, params={"dates": d.strftime("%Y%m%d")}, timeout=15)
        r.raise_for_status()
        for e in r.json().get("events", []):
            if e["id"] not in seen:
                seen.add(e["id"])
                events.append(e)
        d += timedelta(days=1)
    return events


def cmd_scorers(chat_id: str):
    try:
        from collections import defaultdict
        stats = defaultdict(lambda: {"goals": 0, "assists": 0, "team": ""})
        events = fetch_all_espn_events()
        finished = [e for e in events if e["status"]["type"]["name"] == "STATUS_FULL_TIME"]
        if not finished:
            reply(chat_id, t("no_finished"))
            return
        for event in finished:
            r = requests.get(
                "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary",
                params={"event": event["id"]}, timeout=15
            )
            r.raise_for_status()
            for ke in r.json().get("keyEvents", []):
                if not ke.get("scoringPlay"):
                    continue
                text = ke.get("text", "")
                # Goal scorer: "Goal! Team X, Team Y. Player Name (Team) ..."
                m = re.search(r"\. ([^(]+) \(([^)]+)\)", text)
                if m:
                    player = m.group(1).strip()
                    team   = m.group(2).strip()
                    stats[player]["goals"]  += 1
                    stats[player]["team"]    = team
                # Assist: "Assisted by Player Name."
                a = re.search(r"Assisted by ([^.]+)\.", text)
                if a:
                    assistant = a.group(1).strip()
                    # Find team from same event competitors
                    if assistant not in stats:
                        stats[assistant]["team"] = ke.get("team", {}).get("displayName", "")
                    stats[assistant]["assists"] += 1
        if not stats:
            reply(chat_id, t("no_scorers"))
            return
        # Sort: goals desc, assists desc, name asc
        sorted_stats = sorted(
            stats.items(),
            key=lambda x: (-x[1]["goals"], -x[1]["assists"], x[0])
        )
        top10 = sorted_stats[:10]
        lines = [t("scorers_hdr") + "\n`# Player              G  A`"]
        prev = None
        display_rank = 0
        for player, info in top10:
            key = (info["goals"], info["assists"])
            if key != prev:
                display_rank += 1
                prev = key
            g = info["goals"]
            a = info["assists"]
            team = info["team"]
            lines.append(f"{display_rank}. *{player}* {flag(team)} — ⚽ {g}  🎯 {a}")
        reply(chat_id, "\n".join(lines))
    except Exception as e:
        reply(chat_id, f"❌ Error fetching scorers: {e}")
        print(f"[cmd_scorers] ❌ {e}")


def cmd_groups(chat_id: str):
    try:
        data = football_api("/competitions/WC/standings")
        standings = data.get("standings", [])
        if not standings:
            reply(chat_id, t("standings_na2"))
            return

        pos_icons = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣"}
        groups = []
        for standing in standings:
            group_name = (standing.get("group") or "").replace("_", " ").title()
            if not group_name:
                continue
            lines = [f"*{group_name}*"]
            for row in standing["table"]:
                pos  = row["position"]
                name = row["team"]["name"]
                f_   = flag(name)
                pts  = row["points"]
                w, d, l = row["won"], row["draw"], row["lost"]
                gd   = row["goalDifference"]
                gd_s = f"+{gd}" if gd > 0 else str(gd)
                icon = pos_icons.get(pos, f"{pos}.")
                lines.append(f"{icon} {f_} {name} — {pts} pts ({w}W {d}D {l}L {gd_s})")
            groups.append("\n".join(lines))

        mid  = len(groups) // 2
        msg1 = "\n\n".join(groups[:mid])
        msg2 = "\n\n".join(groups[mid:])
        send_md(t("groups_hdr") + "\n\n" + msg1, chat_id)
        time.sleep(0.5)
        send_md(msg2, chat_id)
    except Exception as e:
        reply(chat_id, f"❌ Error: {e}")
        print(f"[cmd_groups] ❌ {e}")


def fetch_match_events(event_id: str) -> list:
    """Fetch keyEvents for a single ESPN event."""
    r = requests.get(
        "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary",
        params={"event": event_id}, timeout=15
    )
    r.raise_for_status()
    return r.json().get("keyEvents", [])


def espn_home_away(event: dict):
    comp = event["competitions"][0]
    home_c = next((c for c in comp["competitors"] if c["homeAway"] == "home"), comp["competitors"][0])
    away_c = next((c for c in comp["competitors"] if c["homeAway"] == "away"), comp["competitors"][1])
    return home_c, away_c


def cmd_goals(chat_id: str):
    """Goals in today's matches."""
    try:
        lines = [t("goals_hdr") + "\n"]
        found = False
        today_pt = now_pt().date()
        for event in fetch_espn_events():
            if event["status"]["type"]["name"] == "STATUS_SCHEDULED":
                continue
            # Filter to today PT only
            event_dt = datetime.fromisoformat(event["date"].replace("Z", "+00:00")).astimezone(LOCAL_TZ)
            if event_dt.date() != today_pt:
                continue
            home_c, away_c = espn_home_away(event)
            home = home_c["team"]["displayName"]
            away = away_c["team"]["displayName"]
            match_goals = []
            for ke in fetch_match_events(event["id"]):
                if not ke.get("scoringPlay"):
                    continue
                text   = ke.get("text", "")
                minute = ke.get("clock", {}).get("displayValue", "?")
                m = re.search(r"\. ([^(]+) \(([^)]+)\)", text)
                if m:
                    scorer = m.group(1).strip()
                    team   = m.group(2).strip()
                    match_goals.append(f"  ⚽ {minute}\' *{scorer}* ({flag(team)} {team})")
            if match_goals:
                h = int(home_c.get("score") or 0)
                a = int(away_c.get("score") or 0)
                lines.append(f"{team_str(home)} {h}–{a} {team_str(away)}")
                lines.extend(match_goals)
                lines.append("")
                found = True
        if not found:
            reply(chat_id, t("no_goals"))
            return
        reply(chat_id, "\n".join(lines))
    except Exception as e:
        reply(chat_id, f"❌ Error: {e}")
        print(f"[cmd_goals] ❌ {e}")


def cmd_red(chat_id: str):
    """Red cards in the tournament."""
    try:
        lines = [t("red_hdr") + "\n"]
        found = False
        for event in fetch_all_espn_events():
            if event["status"]["type"]["name"] == "STATUS_SCHEDULED":
                continue
            home_c, away_c = espn_home_away(event)
            home = home_c["team"]["displayName"]
            away = away_c["team"]["displayName"]
            for ke in fetch_match_events(event["id"]):
                type_text = ke.get("type", {}).get("text", "").lower()
                type_type = ke.get("type", {}).get("type", "").lower()
                is_red = ("red card" in type_text or type_type == "red-card" or "second yellow" in type_text)
                if not is_red:
                    continue
                if ke.get("scoringPlay") or "var" in type_type:
                    continue
                text    = ke.get("text", "")
                minute  = ke.get("clock", {}).get("displayValue", "?")
                p_team  = ke.get("team", {}).get("displayName", "")
                m = re.search(r"^([^(]+?) \(", text)
                player  = m.group(1).strip() if m else text[:25]
                card    = "🟨🟨" if "second yellow" in type_text else "🟥"
                lines.append(f"{card} {minute}\' *{player}* ({flag(p_team)} {p_team})")
                lines.append(f"   {team_str(home)} vs {team_str(away)}\n")
                found = True
        if not found:
            reply(chat_id, t("no_red"))
            return
        reply(chat_id, "\n".join(lines))
    except Exception as e:
        reply(chat_id, f"❌ Error: {e}")
        print(f"[cmd_red] ❌ {e}")


def cmd_team(chat_id: str, query: str):
    """Full team overview: standing + next match + recent results."""
    if not query:
        reply(chat_id, t("usage_team"))
        return
    try:
        all_m = fetch_openfootball()
        team  = find_team(query, all_m)
        if not team:
            reply(chat_id, t("team_not_found", query=query))
            return

        lines = [f"*{team_str(team)}*\n"]

        # Standing
        try:
            data = football_api("/competitions/WC/standings")
            q    = query.strip().lower()
            srch = {q, STANDINGS_ALIASES.get(q, q), team.lower()}
            for standing in data.get("standings", []):
                for row in standing["table"]:
                    api_name = row["team"]["name"].lower()
                    if any(t in api_name or api_name in t for t in srch):
                        group_name = (standing.get("group") or "").replace("_", " ").title()
                        pos  = row["position"]
                        pts  = row["points"]
                        w, d, l = row["won"], row["draw"], row["lost"]
                        gd   = row["goalDifference"]
                        gd_s = f"+{gd}" if gd > 0 else str(gd)
                        icons = {1:"🥇",2:"🥈",3:"🥉",4:"4️⃣"}
                        lines.append(f"📊 *{group_name}* — {icons.get(pos,str(pos)+'.')} place | {pts} pts | {w}W {d}D {l}L | GD {gd_s}")
                        break
        except Exception:
            pass

        # Next match
        now_t = now_pt()
        upcoming = sorted(
            [m for m in all_m if (m["team1"]==team or m["team2"]==team) and to_local_dt(m["date"],m["time"])>now_t],
            key=lambda m: to_local_dt(m["date"],m["time"])
        )
        if upcoming:
            m    = upcoming[0]
            kick = to_local_dt(m["date"], m["time"])
            diff = kick - now_t
            days = diff.days
            hrs, rem = divmod(diff.seconds, 3600)
            mins = rem // 60
            countdown = f"{days}d {hrs}h" if days > 0 else (f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m")
            opp  = m["team2"] if m["team1"]==team else m["team1"]
            lines.append(f"\n⏭ *Next:* vs {team_str(opp)}")
            lines.append(f"   📅 {kick.strftime('%b %-d')} | 🕐 {kick.strftime('%I:%M %p')} PT | ⏳ in {countdown}")

        # Recent results from ESPN
        try:
            q    = query.strip().lower()
            srch = {q, STANDINGS_ALIASES.get(q, q), team.lower()}
            results = []
            for event in fetch_all_espn_events():
                if event["status"]["type"]["name"] != "STATUS_FULL_TIME":
                    continue
                home_c, away_c = espn_home_away(event)
                home = home_c["team"]["displayName"]
                away = away_c["team"]["displayName"]
                if not any(t in home.lower() or t in away.lower() for t in srch):
                    continue
                h = int(home_c.get("score") or 0)
                a = int(away_c.get("score") or 0)
                is_home = any(t in home.lower() for t in srch)
                my_g, op_g = (h, a) if is_home else (a, h)
                opp_name = away if is_home else home
                res = "W" if my_g > op_g else ("D" if my_g == op_g else "L")
                emoji = {"W":"✅","D":"🟡","L":"❌"}[res]
                results.append(f"  {emoji} {res} {my_g}–{op_g} vs {team_str(opp_name)}")
            if results:
                lines.append(f"\n{t('recent')}")
                lines.extend(results[-5:])
        except Exception:
            pass

        # Yellow cards for this team
        try:
            all_cards = collect_yellow_cards()
            q = query.strip().lower()
            srch = {q, STANDINGS_ALIASES.get(q, q), team.lower()}
            team_cards = []
            for t_name, t_cards in all_cards.items():
                if any(s in t_name.lower() or t_name.lower() in s for s in srch):
                    team_cards = t_cards
                    break
            if team_cards:
                lines.append(f"\n🟨 *Yellow cards ({len(team_cards)}):*")
                for c in team_cards:
                    lines.append(f"  🟨 {c['minute']}\' {c['player']}")
        except Exception:
            pass

        reply(chat_id, "\n".join(lines))
    except Exception as e:
        reply(chat_id, f"❌ Error: {e}")
        print(f"[cmd_team] ❌ {e}")




def load_subscribers() -> list:
    subs = load_json(SUBSCRIBERS_FILE)
    if not subs:
        subs = [CHAT_ID]
        save_json(SUBSCRIBERS_FILE, subs)
    return subs

def broadcast_plain(text: str):
    for cid in load_subscribers():
        send_plain(text, cid)

def broadcast_md(text: str):
    for cid in load_subscribers():
        send_md(text, cid)


def set_commands_for_chat(chat_id: str, lang: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"
    payload = {
        "commands": _build_commands(lang),
        "scope": {"type": "chat", "chat_id": int(chat_id)}
    }
    requests.post(url, json=payload, timeout=10)

def cmd_localization(chat_id: str, arg: str):
    cur = get_user_lang(chat_id)
    if not arg:
        reply(chat_id, f"Current language: *{'English' if cur == 'en' else 'Русский'}*\n\n/localization en — English\n/localization ru — Русский")
        return
    lang = arg.lower().strip()
    if lang not in ("en", "ru"):
        reply(chat_id, "Usage: /localization en  or  /localization ru")
        return
    set_user_lang(chat_id, lang)
    _user_ctx.lang = lang
    set_commands_for_chat(chat_id, lang)
    if lang == "ru":
        reply(chat_id, "Язык переключён на *Русский* 🇷🇺")
    else:
        reply(chat_id, "Language switched to *English* 🇬🇧")

def cmd_timezone(chat_id: str, arg: str):
    if not arg:
        tz = get_user_tz(chat_id)
        popular = [
            "PT (UTC-7) — /timezone pt",
            "MT (UTC-6) — /timezone mt",
            "CT (UTC-5) — /timezone ct",
            "ET (UTC-4) — /timezone et",
            "Sao Paulo (UTC-3) — /timezone brazil",
            "Buenos Aires (UTC-3) — /timezone argentina",
            "GMT (UTC+0) — /timezone gmt",
            "London (UTC+1) — /timezone london",
            "Paris (UTC+2) — /timezone paris",
            "Berlin (UTC+2) — /timezone berlin",
            "Moscow (UTC+3) — /timezone moscow",
            "Minsk (UTC+3) — /timezone minsk",
            "Kyiv (UTC+2/3) — /timezone kyiv",
            "Dubai (UTC+4) — /timezone dubai",
            "Tokyo (UTC+9) — /timezone tokyo",
            "Seoul (UTC+9) — /timezone korea",
        ]
        reply(chat_id, f"*Current timezone:* {tz_label(tz)}\n\nSet with: /timezone moscow\n\n" + "\n".join(popular))
        return
    key = arg.lower().strip()
    tz_name = TZ_ALIASES.get(key, arg)  # allow full names like "Europe/Moscow" too
    if set_user_tz(chat_id, tz_name):
        tz = get_user_tz(chat_id)
        now_str = datetime.now(tz).strftime("%I:%M %p")
        reply(chat_id, f"Timezone set to *{tz_name}* ({tz_label(tz)})\nCurrent time: {now_str}")
    else:
        reply(chat_id, f"Unknown timezone: {arg}\nTry: /timezone moscow, /timezone et, /timezone london")

def cmd_subscribe(chat_id: str):
    subs = load_subscribers()
    if chat_id not in subs:
        subs.append(chat_id)
        save_json(SUBSCRIBERS_FILE, subs)
        reply(chat_id, t("subscribed"))
    else:
        reply(chat_id, t("already_sub"))

def cmd_unsubscribe(chat_id: str):
    subs = load_subscribers()
    if chat_id in subs:
        subs.remove(chat_id)
        save_json(SUBSCRIBERS_FILE, subs)
        reply(chat_id, t("unsubscribed"))
    else:
        reply(chat_id, t("not_sub"))

def cmd_teams(chat_id: str):
    """List all team names usable in bot commands."""
    try:
        all_m = fetch_openfootball()
        all_teams = sorted({m["team1"] for m in all_m} | {m["team2"] for m in all_m})
        teams = [tm for tm in all_teams if flag(tm) != "🏳️"]
        lines = [t("teams_hdr"), f"_{t('teams_hint')}_\n"]
        for team in teams:
            lines.append(f"{flag(team)} {team}")
        reply(chat_id, "\n".join(lines))
    except Exception as e:
        reply(chat_id, f"❌ Error: {e}")

def cmd_teams(chat_id: str):
    """List all team names usable in bot commands."""
    try:
        all_m = fetch_openfootball()
        all_teams = sorted({m["team1"] for m in all_m} | {m["team2"] for m in all_m})
        teams = [tm for tm in all_teams if flag(tm) != "🏳️"]
        lines = [t("teams_hdr"), f"_{t('teams_hint')}_\n"]
        for team in teams:
            lines.append(f"{flag(team)} {team}")
        reply(chat_id, "\n".join(lines))
    except Exception as e:
        reply(chat_id, f"❌ Error: {e}")

def cmd_bracket(chat_id: str):
    """Knockout stage bracket."""
    try:
        stages = ["LAST_16","QUARTER_FINAL","SEMI_FINAL","THIRD_PLACE","FINAL"]
        stage_names = {
            "LAST_16":       "🔵 Round of 16",
            "QUARTER_FINAL": "🟡 Quarter-finals",
            "SEMI_FINAL":    "🟠 Semi-finals",
            "THIRD_PLACE":   "🥉 Third Place",
            "FINAL":         "🏆 Final",
        }
        all_matches = []
        for stage in stages:
            data = football_api("/competitions/WC/matches", {"stage": stage})
            all_matches.extend(data.get("matches", []))

        if not all_matches:
            reply(chat_id, t("bracket_wait"))
            return

        lines = [t("bracket_hdr") + "\n"]
        current_stage = None
        for m in all_matches:
            stage = m.get("stage", "")
            if stage != current_stage:
                current_stage = stage
                lines.append(f"\n{stage_names.get(stage, stage)}")
            home   = m["homeTeam"].get("name", "TBD")
            away   = m["awayTeam"].get("name", "TBD")
            status = m["status"]
            if status == "FINISHED":
                sc = m["score"]["fullTime"]
                lines.append(f"🏁 {team_str(home)} {sc['home']}–{sc['away']} {team_str(away)}")
            elif status in ("IN_PLAY","PAUSED"):
                sc = m["score"].get("fullTime") or m["score"].get("halfTime") or {}
                lines.append(f"🔴 {team_str(home)} {sc.get('home','?')}–{sc.get('away','?')} {team_str(away)}")
            else:
                from datetime import datetime as _dt
                kick = _dt.fromisoformat(m["utcDate"].replace("Z","+00:00")).astimezone(LOCAL_TZ)
                lines.append(f"📅 {kick.strftime('%b %-d')} {kick.strftime('%I:%M %p')} PT — {team_str(home)} vs {team_str(away)}")
        reply(chat_id, "\n".join(lines))
    except Exception as e:
        reply(chat_id, f"❌ Error: {e}")
        print(f"[cmd_bracket] ❌ {e}")


def collect_yellow_cards() -> dict:
    """Returns {team_name: [{"player": ..., "minute": ..., "match": ...}]}"""
    from collections import defaultdict
    cards = defaultdict(list)
    for event in fetch_all_espn_events():
        if event["status"]["type"]["name"] == "STATUS_SCHEDULED":
            continue
        home_c, away_c = espn_home_away(event)
        home = home_c["team"]["displayName"]
        away = away_c["team"]["displayName"]
        match_str = f"{team_str(home)} vs {team_str(away)}"
        for ke in fetch_match_events(event["id"]):
            if ke.get("type", {}).get("type", "").lower() != "yellow-card":
                continue
            text   = ke.get("text", "")
            minute = ke.get("clock", {}).get("displayValue", "?")
            p_team = ke.get("team", {}).get("displayName", "")
            m = re.search(r"^([^(]+?) \(", text)
            player = m.group(1).strip() if m else text[:30]
            if p_team:
                cards[p_team].append({"player": player, "minute": minute, "match": match_str})
    return cards


def cmd_yellow(chat_id: str):
    """Top 15 teams by yellow cards in the tournament."""
    try:
        cards = collect_yellow_cards()
        if not cards:
            reply(chat_id, t("no_yellow"))
            return
        sorted_teams = sorted(cards.items(), key=lambda x: len(x[1]), reverse=True)[:15]
        lines = [t("yellow_hdr") + "\n"]
        prev = None
        prev_n = None
        display_rank = 0
        real_rank = 0
        for team_name, team_cards in sorted_teams:
            real_rank += 1
            n = len(team_cards)
            if n != prev:
                display_rank += 1
                prev = n
            lines.append(f"{display_rank}. {flag(team_name)} *{team_name}* — {n} 🟨")
        reply(chat_id, "\n".join(lines))
    except Exception as e:
        reply(chat_id, f"❌ Error: {e}")
        print(f"[cmd_yellow] ❌ {e}")

def cmd_live(chat_id: str):
    live = []
    for event in fetch_espn_events():
        if event["status"]["type"]["name"] not in LIVE_STATUSES:
            continue
        comp   = event["competitions"][0]
        home_c = next((c for c in comp["competitors"] if c["homeAway"] == "home"), comp["competitors"][0])
        away_c = next((c for c in comp["competitors"] if c["homeAway"] == "away"), comp["competitors"][1])
        home   = home_c["team"]["displayName"]
        away   = away_c["team"]["displayName"]
        h      = int(home_c.get("score") or 0)
        a      = int(away_c.get("score") or 0)
        minute = event["status"].get("displayClock", "?")
        live.append(f"{team_str(home)} *{h}–{a}* {team_str(away)}  _{minute}'_")

    if not live:
        reply(chat_id, t("no_live"))
        return
    reply(chat_id, t("live_header") + "\n\n" + "\n".join(live))


# ── Bot menu setup ────────────────────────

def _build_commands(lang: str) -> list:
    _user_ctx.lang = lang
    return [
        {"command": "today",        "description": t("cmd_today")},
        {"command": "live",         "description": t("cmd_live")},
        {"command": "schedule",     "description": t("cmd_schedule")},
        {"command": "next",         "description": t("cmd_next")},
        {"command": "standings",    "description": t("cmd_standings")},
        {"command": "scorers",      "description": t("cmd_scorers")},
        {"command": "goals",        "description": t("cmd_goals")},
        {"command": "groups",       "description": t("cmd_groups")},
        {"command": "red",          "description": t("cmd_red")},
        {"command": "yellow",       "description": t("cmd_yellow")},
        {"command": "team",         "description": t("cmd_team")},
        {"command": "teams",        "description": t("cmd_teams")},
        {"command": "bracket",      "description": t("cmd_bracket")},
        {"command": "subscribe",    "description": t("cmd_subscribe")},
        {"command": "unsubscribe",  "description": t("cmd_unsubscribe")},
        {"command": "timezone",     "description": t("cmd_timezone")},
        {"command": "localization", "description": t("cmd_localization")},
    ]

def set_commands():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"
    # English (default)
    r = requests.post(url, json={"commands": _build_commands("en")}, timeout=10)
    if r.ok:
        print("✅ Bot command menu set (EN)")
    else:
        print(f"⚠️  Could not set commands (EN): {r.text}")
    # Russian
    r = requests.post(url, json={"commands": _build_commands("ru"), "language_code": "ru"}, timeout=10)
    if r.ok:
        print("✅ Bot command menu set (RU)")
    else:
        print(f"⚠️  Could not set commands (RU): {r.text}")


# ── Telegram polling ──────────────────────

def handle_update(update: dict):
    msg = update.get("message") or update.get("channel_post")
    if not msg:
        return
    text    = msg.get("text", "").strip()
    chat_id = str(msg["chat"]["id"])
    _user_ctx.lang = get_user_lang(chat_id)
    if not text.startswith("/"):
        return
    # Access log
    frm      = msg.get("from", {})
    username = frm.get("username") or frm.get("first_name", "?")
    lang     = frm.get("language_code", "?")
    ts       = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M PT")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "access.log"), "a") as _f:
        _f.write(f"{ts} | chat={chat_id} | user={username} | lang={lang} | cmd={text[:40]}\n")

    parts   = text.split(maxsplit=1)
    cmd     = parts[0].split("@")[0].lower()  # strip @botname suffix
    arg     = parts[1].strip() if len(parts) > 1 else ""

    try:
        if cmd == "/today":
            cmd_today(chat_id)
        elif cmd == "/schedule":
            cmd_schedule(chat_id, arg)
        elif cmd == "/next":
            cmd_next(chat_id, arg)
        elif cmd == "/standings":
            cmd_standings(chat_id, arg)
        elif cmd == "/live":
            cmd_live(chat_id)
        elif cmd == "/scorers":
            cmd_scorers(chat_id)
        elif cmd == "/groups":
            cmd_groups(chat_id)
        elif cmd == "/goals":
            cmd_goals(chat_id)
        elif cmd == "/red":
            cmd_red(chat_id)
        elif cmd == "/yellow":
            cmd_yellow(chat_id)
        elif cmd == "/team":
            cmd_team(chat_id, arg)
        elif cmd == "/bracket":
            cmd_bracket(chat_id)
        elif cmd == "/teams":
            cmd_teams(chat_id)
        elif cmd == "/subscribe":
            cmd_subscribe(chat_id)
        elif cmd == "/timezone":
            cmd_timezone(chat_id, arg)
        elif cmd == "/localization":
            cmd_localization(chat_id, arg)
        elif cmd == "/unsubscribe":
            cmd_unsubscribe(chat_id)
    except Exception as e:
        send_plain(f"❌ Error: {e}", chat_id)
        print(f"[cmd {cmd}] ❌ {e}")


def polling_loop():
    offset = None
    print("👂 Listening for commands...")
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message"]}
            if offset:
                params["offset"] = offset
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params=params, timeout=40
            )
            for upd in r.json().get("result", []):
                offset = upd["update_id"] + 1
                handle_update(upd)
        except Exception as e:
            print(f"[polling] ❌ {e}")
            time.sleep(5)


# ── Setup chat ID helper ──────────────────

def get_chat_id():
    print("Send your bot any message, then press Enter...")
    input()
    r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", timeout=10).json()
    results = r.get("result", [])
    if not results:
        print("❌ No messages. Make sure you messaged the bot and the token is correct.")
        return
    for upd in results[-3:]:
        msg  = upd.get("message") or upd.get("channel_post", {})
        chat = msg.get("chat", {})
        print(f"  chat_id = {chat.get('id')}  ({chat.get('type')} / {chat.get('username') or chat.get('title') or chat.get('first_name')})")


# ── Entry point ───────────────────────────

if __name__ == "__main__":
    if "--get-chat-id" in sys.argv:
        get_chat_id()
        sys.exit(0)

    if not all([BOT_TOKEN, CHAT_ID, FOOTBALL_API_KEY]):
        print("❌ Fill in BOT_TOKEN, CHAT_ID and FOOTBALL_API_KEY in .env file!")
        sys.exit(1)

    print("🤖 World Cup 2026 bot starting...")
    set_commands()

    # Run immediately on start
    job_schedule()
    job_results()

    # Schedules
    schedule.every().day.at(SEND_TIME).do(job_schedule)
    schedule.every(5).minutes.do(job_results)
    schedule.every(2).minutes.do(job_live)
    schedule.every(1).minutes.do(job_reminders)

    print(f"   📅 Daily schedule at {SEND_TIME} PT")
    print(f"   🏁 Results every 5 min")
    print(f"   ⚽ Live updates every 2 min")
    print(f"   ⏰ Reminders 30 min before kickoff")
    print(f"   💬 Commands: /today /schedule /next /standings /live")
    print("   (Ctrl+C to stop)\n")

    threading.Thread(target=polling_loop, daemon=True).start()

    while True:
        schedule.run_pending()
        time.sleep(30)
