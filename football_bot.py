#!/usr/bin/env python3
"""
Jalgpalli Ennustus Telegram Bot — PRO VERSIOON
Odds + Uudised + Mängijate andmed + Automaatne päevane skannimine
"""

import requests
from datetime import datetime, timezone, timedelta
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ══════════════════════════════════════════════════════════════
# ▶  SINU API VÕTMED — täida kõik väljad
# ══════════════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN  = "SINU_BOTI_TOKEN_SIIA"
GROQ_API_KEY        = "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"
ODDS_API_KEY        = "b88ee2f550d84d79cb66c1c45e0843ea"  # the-odds-api.com
NEWS_API_KEY        = "daa69dc1b60541fdb5d24458eabbc3ae"  # newsapi.org
API_FOOTBALL_KEY    = "0bdce33132mshe8ef5e7f6499c67p1ecf3bjsn21627e33ef2b"  # rapidapi.com
# ══════════════════════════════════════════════════════════════

client = Groq(api_key=GROQ_API_KEY)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_V2   = "https://site.api.espn.com/apis/v2/sports/soccer"
HEADERS   = {"User-Agent": "Mozilla/5.0"}

LEAGUES = {
    "MM": "fifa.world", "WC": "fifa.world",
    "EM": "uefa.euro",  "EURO": "uefa.euro",
    "NL": "uefa.nations",
    "CL": "uefa.champions", "UCL": "uefa.champions",
    "EL": "uefa.europa",    "UEL": "uefa.europa",
    "PL": "eng.1", "EPL": "eng.1", "PREMIER": "eng.1",
    "BUNDES": "ger.1", "BUNDESLIGA": "ger.1",
    "LALIGA": "esp.1",
    "SERIEA": "ita.1",
    "LIGUE1": "fra.1",
    "EREDIVISIE": "ned.1",
}

LEAGUE_NAMES = {
    "fifa.world": "🌍 FIFA MM",
    "uefa.euro": "🇪🇺 Euroopa Meistrivõistlused",
    "uefa.nations": "🏆 Rahvuste Liiga",
    "uefa.champions": "⭐ Meistrite Liiga",
    "uefa.europa": "🟠 Euroopa Liiga",
    "eng.1": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "ger.1": "🇩🇪 Bundesliga",
    "esp.1": "🇪🇸 La Liga",
    "ita.1": "🇮🇹 Serie A",
    "fra.1": "🇫🇷 Ligue 1",
    "ned.1": "🇳🇱 Eredivisie",
}

# Odds API liigakoodid
ODDS_SPORTS = {
    "fifa.world": "soccer_fifa_world_cup",
    "uefa.champions": "soccer_uefa_champs_league",
    "uefa.europa": "soccer_uefa_europa_league",
    "eng.1": "soccer_epl",
    "ger.1": "soccer_germany_bundesliga",
    "esp.1": "soccer_spain_la_liga",
    "ita.1": "soccer_italy_serie_a",
    "fra.1": "soccer_france_ligue_one",
}

# API-Football liigakoodid
APIFOOTBALL_LEAGUES = {
    "fifa.world": 1,
    "uefa.champions": 2,
    "uefa.europa": 3,
    "eng.1": 39,
    "ger.1": 78,
    "esp.1": 140,
    "ita.1": 135,
    "fra.1": 61,
}


# ══════════════════════════════════════════════════════════════
# ESPN — MÄNGUD JA SEIS
# ══════════════════════════════════════════════════════════════

def find_league(text: str) -> str:
    text_up = text.upper()
    for key, code in LEAGUES.items():
        if key in text_up:
            return code
    return "fifa.world"


def get_today_matches(league_code: str) -> list:
    """Toob TÄNASED mängud ESPN-ist."""
    try:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        url = f"{ESPN_BASE}/{league_code}/scoreboard?dates={today}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        return _parse_matches(r.json().get("events", []))
    except Exception:
        return []


def get_upcoming_matches(league_code: str, limit: int = 8) -> list:
    try:
        r = requests.get(f"{ESPN_BASE}/{league_code}/scoreboard", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        return _parse_matches(r.json().get("events", [])[:limit])
    except Exception:
        return []


def _parse_matches(events: list) -> list:
    matches = []
    for e in events:
        comp = e.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue
        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
        status = e.get("status", {}).get("type", {})
        date_str = e.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            date_fmt = dt.strftime("%d.%m %H:%M")
        except Exception:
            date_fmt = date_str[:10]

        matches.append({
            "home": home.get("team", {}).get("displayName", "?"),
            "away": away.get("team", {}).get("displayName", "?"),
            "home_abbr": home.get("team", {}).get("abbreviation", "?"),
            "away_abbr": away.get("team", {}).get("abbreviation", "?"),
            "date": date_fmt,
            "score_home": home.get("score", "-"),
            "score_away": away.get("score", "-"),
            "completed": status.get("completed", False),
            "in_progress": status.get("name", "") == "STATUS_IN_PROGRESS",
            "venue": comp.get("venue", {}).get("fullName", ""),
            "league_code": "",
        })
    return matches


def get_standings(league_code: str) -> list:
    try:
        url = f"{ESPN_V2}/{league_code}/standings"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        standings = []
        groups = data.get("children", [data])
        for group in groups:
            entries = group.get("standings", {}).get("entries", [])
            group_name = group.get("name", "")
            for entry in entries:
                stats = {s["name"]: s.get("displayValue", s.get("value", 0))
                         for s in entry.get("stats", [])}
                standings.append({
                    "team": entry.get("team", {}).get("displayName", "?"),
                    "abbr": entry.get("team", {}).get("abbreviation", "?"),
                    "group": group_name,
                    "played":  stats.get("gamesPlayed", stats.get("played", 0)),
                    "wins":    stats.get("wins", 0),
                    "draws":   stats.get("ties", stats.get("draws", 0)),
                    "losses":  stats.get("losses", 0),
                    "gf":      stats.get("pointsFor", stats.get("goalsFor", 0)),
                    "ga":      stats.get("pointsAgainst", stats.get("goalsAgainst", 0)),
                    "gd":      stats.get("pointDifferential", stats.get("goalDifference", 0)),
                    "points":  stats.get("points", 0),
                })
        return standings
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# THE ODDS API — KOEFITSIENDID
# ══════════════════════════════════════════════════════════════

def get_odds(home: str, away: str, league_code: str = "") -> dict:
    """
    Toob mängu koefitsiendid The Odds API-st.
    Tagastab: {home_odds, draw_odds, away_odds, bookmakers, implied_home_pct, implied_away_pct}
    """
    if not ODDS_API_KEY or ODDS_API_KEY == "SINU_ODDS_API_KEY":
        return {}

    sport = ODDS_SPORTS.get(league_code, "soccer_epl")
    try:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal",
            },
            timeout=10
        )
        if r.status_code != 200:
            return {}

        events = r.json()
        home_l = home.lower()
        away_l = away.lower()

        for event in events:
            ht = event.get("home_team", "").lower()
            at = event.get("away_team", "").lower()
            # Leia kõige sarnasem mäng
            if (any(w in ht for w in home_l.split() if len(w) > 3) or
                any(w in home_l for w in ht.split() if len(w) > 3)):

                bookmakers = event.get("bookmakers", [])
                if not bookmakers:
                    continue

                home_prices, draw_prices, away_prices = [], [], []
                bookie_names = []

                for bookie in bookmakers[:6]:
                    bookie_names.append(bookie.get("title", ""))
                    for market in bookie.get("markets", []):
                        if market.get("key") == "h2h":
                            for outcome in market.get("outcomes", []):
                                name = outcome.get("name", "").lower()
                                price = outcome.get("price", 0)
                                if any(w in name for w in ht.split() if len(w) > 3):
                                    home_prices.append(price)
                                elif "draw" in name:
                                    draw_prices.append(price)
                                else:
                                    away_prices.append(price)

                if home_prices and away_prices:
                    avg_home = round(sum(home_prices) / len(home_prices), 2)
                    avg_draw = round(sum(draw_prices) / len(draw_prices), 2) if draw_prices else 0
                    avg_away = round(sum(away_prices) / len(away_prices), 2)
                    total = (1/avg_home) + (1/avg_draw if avg_draw else 0) + (1/avg_away)
                    return {
                        "home_odds": avg_home,
                        "draw_odds": avg_draw,
                        "away_odds": avg_away,
                        "bookmakers": ", ".join(bookie_names[:4]),
                        "implied_home_pct": round((1/avg_home) / total * 100, 1),
                        "implied_draw_pct": round((1/avg_draw) / total * 100, 1) if avg_draw else 0,
                        "implied_away_pct": round((1/avg_away) / total * 100, 1),
                    }
    except Exception:
        pass
    return {}


# ══════════════════════════════════════════════════════════════
# NEWS API — MEESKONNA UUDISED
# ══════════════════════════════════════════════════════════════

def get_team_news(team: str, days_back: int = 7) -> list:
    """
    Toob meeskonna viimased uudised NewsAPI-st.
    """
    if not NEWS_API_KEY or NEWS_API_KEY == "SINU_NEWS_API_KEY":
        return []
    try:
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": f"{team} football soccer",
                "from": from_date,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": 5,
                "apiKey": NEWS_API_KEY,
            },
            timeout=8
        )
        if r.status_code != 200:
            return []
        articles = r.json().get("articles", [])
        return [
            {
                "title": a.get("title", ""),
                "description": a.get("description", "") or "",
                "source": a.get("source", {}).get("name", ""),
                "date": a.get("publishedAt", "")[:10],
            }
            for a in articles if a.get("title")
        ]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# API-FOOTBALL — MÄNGIJATE JA MEESKONNA STATISTIKA
# ══════════════════════════════════════════════════════════════

def get_team_stats(team_name: str, league_code: str = "eng.1") -> dict:
    """
    Toob meeskonna statistika Free API Live Football Data kaudu (Smart API / RapidAPI).
    """
    if not API_FOOTBALL_KEY:
        return {}

    headers = {
        "X-RapidAPI-Key": API_FOOTBALL_KEY,
        "X-RapidAPI-Host": "free-api-live-football-data.p.rapidapi.com",
    }

    try:
        # Otsi meeskond
        r = requests.get(
            "https://free-api-live-football-data.p.rapidapi.com/football-search-teams",
            params={"term": team_name},
            headers=headers, timeout=8
        )
        if r.status_code != 200:
            return {}

        data = r.json()
        teams = data.get("response", {}).get("teams", [])
        if not teams:
            return {}

        team = teams[0]
        team_id = team.get("id")
        team_display = team.get("name", team_name)
        country = team.get("country", "")

        # Meeskonna viimased mängud (vorm)
        rf = requests.get(
            "https://free-api-live-football-data.p.rapidapi.com/football-get-team-next-matches",
            params={"teamid": team_id},
            headers=headers, timeout=8
        )

        # Meeskonna mängijad
        rp = requests.get(
            "https://free-api-live-football-data.p.rapidapi.com/football-get-team-players",
            params={"teamid": team_id},
            headers=headers, timeout=8
        )

        players_data = rp.json().get("response", {}) if rp.status_code == 200 else {}
        players = players_data.get("players", [])

        # Leia ründajad ja parimad mängijad
        attackers = [p for p in players if p.get("position", "").upper() in ["ATTACKER", "FORWARD", "STRIKER"]][:3]
        top_players = ", ".join([p.get("name", "") for p in attackers]) if attackers else "N/A"

        # Statistika viimaste mängude põhjal (kui saadaval)
        recent = rf.json().get("response", {}).get("matches", []) if rf.status_code == 200 else []
        form_chars = []
        for m in recent[-5:]:
            home_id = m.get("homeTeam", {}).get("id")
            home_score = m.get("score", {}).get("home", 0) or 0
            away_score = m.get("score", {}).get("away", 0) or 0
            if m.get("status", "") not in ["FT", "AET", "PEN"]:
                continue
            if home_id == team_id:
                form_chars.append("W" if home_score > away_score else ("D" if home_score == away_score else "L"))
            else:
                form_chars.append("W" if away_score > home_score else ("D" if home_score == away_score else "L"))

        form_display = " ".join([
            "🟢" if c == "W" else ("🟡" if c == "D" else "🔴")
            for c in form_chars[-5:]
        ]) if form_chars else "N/A"

        return {
            "team": team_display,
            "country": country,
            "form": form_display,
            "top_scorers": top_players,
            "players_count": len(players),
        }

    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════
# GROQ AI — ENNUSTUSED
# ══════════════════════════════════════════════════════════════

def predict_match_full(home: str, away: str, league_code: str = "") -> dict:
    """
    Kogub kõik andmed (odds, uudised, statistika) ja küsib Groqilt ennustuse.
    Tagastab dict kõigi andmetega koos AI vastusega.
    """
    result = {
        "home": home, "away": away,
        "odds": {}, "home_news": [], "away_news": [],
        "home_stats": {}, "away_stats": {},
        "prediction": "",
    }

    # 1. Odds
    result["odds"] = get_odds(home, away, league_code)

    # 2. Uudised (paralleelselt mõlemale meeskonnale)
    result["home_news"] = get_team_news(home)
    result["away_news"] = get_team_news(away)

    # 3. Statistika
    result["home_stats"] = get_team_stats(home, league_code)
    result["away_stats"] = get_team_stats(away, league_code)

    # 4. Groq — koosta täielik kontekst
    odds_text = ""
    if result["odds"]:
        o = result["odds"]
        odds_text = (
            f"KOEFITSIENDID ({o.get('bookmakers','')}):\n"
            f"  {home}: {o.get('home_odds','N/A')} (impl. {o.get('implied_home_pct','?')}%)\n"
            f"  Viik:   {o.get('draw_odds','N/A')} (impl. {o.get('implied_draw_pct','?')}%)\n"
            f"  {away}: {o.get('away_odds','N/A')} (impl. {o.get('implied_away_pct','?')}%)\n"
        )

    def stats_text(name, s):
        if not s:
            return f"{name}: statistika pole saadaval\n"
        return (
            f"{name} ({s.get('team', name)}):\n"
            f"  Vorm (viimased 5): {s.get('form', 'N/A')}\n"
            f"  Tulemus: {s.get('wins','?')}V {s.get('draws','?')}Vi {s.get('losses','?')}K "
            f"({s.get('played','?')} mängu)\n"
            f"  Väravad: {s.get('goals_for','?')} löödud / {s.get('goals_against','?')} saadud\n"
            f"  Parimad ründajad: {s.get('top_scorers','N/A')}\n"
        )

    def news_text(name, articles):
        if not articles:
            return f"{name} uudised: pole saadaval\n"
        lines = [f"  • [{a['date']}] {a['title']}" for a in articles[:4]]
        return f"{name} viimased uudised:\n" + "\n".join(lines) + "\n"

    full_context = f"""
MÄNG: {home} vs {away}

{odds_text}
{stats_text(home, result['home_stats'])}
{stats_text(away, result['away_stats'])}
{news_text(home, result['home_news'])}
{news_text(away, result['away_news'])}
"""

    prompt = f"""Sa oled maailma parim jalgpallianalüütik. Analüüsi kõiki allpool toodud andmeid.

{full_context}

Anna ennustus EESTI KEELES täpselt selles formaadis:

🔍 VORMIANALÜÜS
[2-3 lauset mõlema meeskonna hetkeseisust, vigastest mängijatest, meeleolust viimaste uudiste põhjal]

⚖️ KOEFITSIENTIDE ANALÜÜS
[Selgita mida bookmaker'id ütlevad. Kas odds on õiglased? Kus on väärtus?]

📊 STATISTIKA ANALÜÜS
[Võrdle meeskondade forme, väravate statistikat, võtmemängijaid]

🎯 ENNUSTUS
Tulemus: [KODU VÕIT / VIIK / KÜLAS VÕIT]
Ennustatav skoor: X:X
Kindlustase: [KÕRGE / KESKMINE / MADAL]

📈 TÕENÄOSUSED
Kodu võit: X%
Viik: X%
Külas võit: X%

💡 PÕHJENDUS
[2-3 peamist põhjust miks see ennustus on õige]

⚠️ RISKID
[Mis võiks ennustuse ümber lükata?]

Ole konkreetne. Kasuta kõiki saadaolevaid andmeid."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    "Sa oled maailma parim jalgpallianalüütik. "
                    "Kasuta kõiki saadaolevaid andmeid. Vasta EESTI KEELES. "
                    "Ole täpne, struktureeritud ja professionaalne."
                )},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200,
        )
        result["prediction"] = response.choices[0].message.content
    except Exception as e:
        result["prediction"] = f"❌ AI ennustus ebaõnnestus: {e}"

    return result


def answer_football_question(question: str) -> str:
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    "Sa oled maailma parim jalgpallianalüütik ja ekspert. "
                    "Vasta EESTI KEELES. Ole täpne ja põhjalik."
                )},
                {"role": "user", "content": question}
            ],
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Viga: {e}"


# ══════════════════════════════════════════════════════════════
# SÕNUMITE VORMISTAMINE — PRO STIIL
# ══════════════════════════════════════════════════════════════

def confidence_bar(pct: float) -> str:
    """Loob visuaalse tõenäosuse riba."""
    filled = int(pct / 10)
    return "█" * filled + "░" * (10 - filled) + f" {pct:.0f}%"


def odds_arrow(home_pct: float, away_pct: float) -> str:
    if home_pct > away_pct + 15:
        return "⬅️ kodu tugevalt favoriit"
    elif home_pct > away_pct + 5:
        return "◀️ kodu favoriit"
    elif away_pct > home_pct + 15:
        return "➡️ külas tugevalt favoriit"
    elif away_pct > home_pct + 5:
        return "▶️ külas favoriit"
    else:
        return "↔️ tasavägine"


def format_full_prediction(r: dict) -> str:
    home = r["home"]
    away = r["away"]
    odds = r.get("odds", {})

    # ── Päis ──────────────────────────────────
    msg = (
        f"╔══════════════════════════════════╗\n"
        f"║  ⚽ MÄNGU ENNUSTUS               ║\n"
        f"╚══════════════════════════════════╝\n\n"
        f"🏠 <b>{home}</b>\n"
        f"        🆚\n"
        f"✈️ <b>{away}</b>\n\n"
    )

    # ── Koefitsiendid ──────────────────────────
    if odds:
        h_pct  = odds.get("implied_home_pct", 0)
        d_pct  = odds.get("implied_draw_pct", 0)
        a_pct  = odds.get("implied_away_pct", 0)
        trend  = odds_arrow(h_pct, a_pct)

        msg += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>BOOKMAKER KOEFITSIENDID</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏠 Kodu:  <b>{odds.get('home_odds','?')}</b>  [{confidence_bar(h_pct)}]\n"
            f"🤝 Viik:  <b>{odds.get('draw_odds','?')}</b>  [{confidence_bar(d_pct)}]\n"
            f"✈️ Külas: <b>{odds.get('away_odds','?')}</b>  [{confidence_bar(a_pct)}]\n"
            f"   {trend}\n"
            f"📌 <i>Allikad: {odds.get('bookmakers','')}</i>\n\n"
        )

    # ── Statistika ──────────────────────────
    def stats_block(name, s, emoji):
        if not s:
            return ""
        return (
            f"{emoji} <b>{name}</b>\n"
            f"   Vorm: {s.get('form','N/A')}\n"
            f"   Rekord: <b>{s.get('wins','?')}V</b> {s.get('draws','?')}Vi <b>{s.get('losses','?')}K</b> "
            f"({s.get('played','?')} mängu)\n"
            f"   Väravad: ⚽{s.get('goals_for','?')} 🥅{s.get('goals_against','?')}\n"
            f"   Tähed: {s.get('top_scorers','N/A')}\n"
        )

    hs = r.get("home_stats", {})
    as_ = r.get("away_stats", {})
    if hs or as_:
        msg += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>MEESKONDADE STATISTIKA</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        msg += stats_block(home, hs, "🏠")
        msg += "\n"
        msg += stats_block(away, as_, "✈️")
        msg += "\n"

    # ── Uudised ──────────────────────────────
    hn = r.get("home_news", [])
    an = r.get("away_news", [])
    if hn or an:
        msg += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📰 <b>VIIMASED UUDISED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        if hn:
            msg += f"<b>{home}:</b>\n"
            for n in hn[:3]:
                msg += f"  • {n['title'][:80]}\n"
            msg += "\n"
        if an:
            msg += f"<b>{away}:</b>\n"
            for n in an[:3]:
                msg += f"  • {n['title'][:80]}\n"
            msg += "\n"

    # ── AI ennustus ──────────────────────────
    msg += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>AI ANALÜÜS &amp; ENNUSTUS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{r.get('prediction','')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚠️ Ennustus põhineb AI + bookmaker andmetel. Mängi vastutustundlikult.</i>"
    )
    return msg


def format_scan_predictions(predictions: list, date_str: str) -> list:
    """Vormistab /skanni tulemused. Tagastab listi sõnumitest (üks mäng = üks sõnum)."""
    messages = []
    header = (
        f"╔══════════════════════════════════╗\n"
        f"║  📅 PÄEVA ENNUSTUSED — {date_str}  ║\n"
        f"╚══════════════════════════════════╝\n"
        f"Analüüsisin <b>{len(predictions)} mängu</b>.\n\n"
    )
    messages.append(header)

    for i, r in enumerate(predictions, 1):
        home = r["home"]
        away = r["away"]
        odds = r.get("odds", {})
        prediction_text = r.get("prediction", "")

        # Lõika kokku lühike versioon skaneerimise jaoks
        h_pct  = odds.get("implied_home_pct", "?")
        d_pct  = odds.get("implied_draw_pct", "?")
        a_pct  = odds.get("implied_away_pct", "?")
        h_odd  = odds.get("home_odds", "?")
        d_odd  = odds.get("draw_odds", "?")
        a_odd  = odds.get("away_odds", "?")

        odds_line = ""
        if odds:
            odds_line = (
                f"📊 Koefitsiendid: "
                f"K<b>{h_odd}</b>({h_pct}%) "
                f"V<b>{d_odd}</b>({d_pct}%) "
                f"A<b>{a_odd}</b>({a_pct}%)\n"
            )

        msg = (
            f"⚽ <b>MÄNG {i}: {home} vs {away}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{odds_line}"
            f"\n{prediction_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        messages.append(msg)

    return messages


def format_matches(matches: list, league_name: str) -> str:
    if not matches:
        return "❌ Mänge ei leitud. Proovi teist liigat või käsku /liigad."

    msg = (
        f"╔══════════════════════════════════╗\n"
        f"║  📅 JÄRGMISED MÄNGUD              ║\n"
        f"╚══════════════════════════════════╝\n"
        f"{league_name}\n\n"
    )

    for m in matches:
        if m["in_progress"]:
            status = f"🔴 <b>LIVE</b> {m['score_home']}:{m['score_away']}"
        elif m["completed"]:
            status = f"✅ Lõppenud <b>{m['score_home']}:{m['score_away']}</b>"
        else:
            status = f"🕐 <b>{m['date']}</b>"

        msg += f"🏠 <b>{m['home']}</b> vs <b>{m['away']}</b> ✈️\n"
        msg += f"   {status}"
        if m.get("venue"):
            msg += f" · {m['venue']}"
        msg += "\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "💡 <i>/ennusta [tiim1] vs [tiim2] — täisanalüüs</i>"
    return msg


def format_standings(standings: list, league_name: str) -> str:
    if not standings:
        return "❌ Seisu ei leitud. Turniir pole alanud või liiga kood vale.\n\nProovi: /liigad"

    msg = (
        f"╔══════════════════════════════════╗\n"
        f"║  🏆 PUNKTISEIS                    ║\n"
        f"╚══════════════════════════════════╝\n"
        f"{league_name}\n\n"
    )

    current_group = None
    for i, t in enumerate(standings[:32], 1):
        if t.get("group") and t["group"] != current_group:
            current_group = t["group"]
            msg += f"\n<b>📌 {current_group}</b>\n"
            msg += "<code> #  Meeskond           M  V  Vi K  GD  Pts</code>\n"

        gd = str(t['gd'])
        if isinstance(t['gd'], (int, float)) and float(str(t['gd'])) > 0:
            gd = f"+{t['gd']}"

        rank_icon = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}. ")
        msg += f"<code>{str(i)+'.':<3} {t['team'][:18]:<18} {str(t['played']):>2} {str(t['wins']):>2} {str(t['draws']):>2} {str(t['losses']):>2} {gd:>4} {str(t['points']):>4}</code>\n"

        if i >= 24 and not t.get("group"):
            break

    msg += "\n<i>M=Mängud V=Võidud Vi=Viigid K=Kaotused GD=Väravad Pts=Punktid</i>"
    return msg


# ══════════════════════════════════════════════════════════════
# TELEGRAM KÄSUD
# ══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ <b>JALGPALLI ENNUSTUS BOT — PRO</b>\n\n"
        "Kasutan <b>ESPN + The Odds API + NewsAPI + API-Football + Groq AI</b> "
        "et anda võimalikult täpne ennustus.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>🔮 ENNUSTUSED</b>\n"
        "/ennusta Brasiilia vs Argentina\n"
        "/skanni [liiga] — tänaste mängude automaatennustus\n\n"
        "<b>📊 INFO</b>\n"
        "/mangud [liiga] — järgmised mängud\n"
        "/seis [liiga] — punktitabel\n"
        "/turniir [liiga] — turniiri ennustus\n"
        "/liigad — kõik toetatud liigad\n\n"
        "<b>💬 VABA TEKST</b>\n"
        "Kirjuta mis tahes jalgpalliküsimus!\n"
        "Nt: <i>Kes on parim ründaja 2026 MM-il?</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <i>Mängi vastutustundlikult.</i>",
        parse_mode=ParseMode.HTML
    )


async def cmd_ennusta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""

    if " vs " in text.lower():
        parts = text.lower().split(" vs ")
        home = parts[0].strip().title()
        away = parts[1].strip().title()
    elif len(context.args) >= 2:
        home = context.args[0].title()
        away = context.args[-1].title()
    else:
        await update.message.reply_text(
            "❌ Kasuta nii:\n<b>/ennusta Arsenal vs Chelsea</b>\n\n"
            "Liiga täpsuseks: <b>/ennusta Arsenal vs Chelsea PL</b>",
            parse_mode=ParseMode.HTML
        )
        return

    # Tuvasta liiga tekstist
    league_code = find_league(text) if text else "eng.1"

    await update.message.reply_text(
        f"🔄 <b>Analüüsin: {home} vs {away}</b>\n\n"
        f"📡 Laen odds, uudised, statistika...",
        parse_mode=ParseMode.HTML
    )

    result = predict_match_full(home, away, league_code)
    msg = format_full_prediction(result)

    if len(msg) > 4000:
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i:i+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_skanni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skannib kõik tänased mängud ja ennustab nende tulemused."""
    text = " ".join(context.args).upper() if context.args else "PL"
    league_code = find_league(text)
    league_name = LEAGUE_NAMES.get(league_code, league_code)
    today = datetime.now().strftime("%d.%m.%Y")

    await update.message.reply_text(
        f"🔄 <b>Skanin tänaseid mänge: {league_name}</b>\n\n"
        f"📡 Laen mänge, odds, uudised, statistika...\n"
        f"⏳ See võtab ~30-60 sekundit.",
        parse_mode=ParseMode.HTML
    )

    matches = get_today_matches(league_code)

    if not matches:
        # Proovi järgmised tulevad mängud kui täna ei ole
        matches = get_upcoming_matches(league_code, limit=5)
        if not matches:
            await update.message.reply_text(
                f"❌ Täna pole {league_name} mänge.\n\n"
                f"Proovi teist liigat: /skanni CL\n"
                f"Või vaata järgmisi: /mangud {text}",
                parse_mode=ParseMode.HTML
            )
            return
        await update.message.reply_text(
            f"ℹ️ Täna pole mänge. Ennustan <b>{len(matches)}</b> järgmist tulevat mängu.",
            parse_mode=ParseMode.HTML
        )

    await update.message.reply_text(
        f"✅ Leitud <b>{len(matches)} mängu</b>. Alustan ennustamist...",
        parse_mode=ParseMode.HTML
    )

    predictions = []
    for m in matches:
        result = predict_match_full(m["home"], m["away"], league_code)
        result["date"] = m.get("date", "")
        result["venue"] = m.get("venue", "")
        predictions.append(result)

    messages = format_scan_predictions(predictions, today)
    for msg in messages:
        if len(msg) > 4000:
            for i in range(0, len(msg), 4000):
                await update.message.reply_text(msg[i:i+4000], parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_mangud(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).upper() if context.args else "PL"
    league_code = find_league(text)
    league_name = LEAGUE_NAMES.get(league_code, league_code)

    await update.message.reply_text(f"📅 Laen {league_name} mänge...", parse_mode=ParseMode.HTML)

    matches = get_upcoming_matches(league_code)
    msg = format_matches(matches, league_name)
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_seis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).upper() if context.args else "PL"
    league_code = find_league(text)
    league_name = LEAGUE_NAMES.get(league_code, league_code)

    await update.message.reply_text(f"🏆 Laen {league_name} seisu...", parse_mode=ParseMode.HTML)

    standings = get_standings(league_code)
    msg = format_standings(standings, league_name)

    if len(msg) > 4000:
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i:i+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_turniir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).upper() if context.args else "MM"
    league_code = find_league(text)
    league_name = LEAGUE_NAMES.get(league_code, league_code)

    await update.message.reply_text(f"🎯 Analüüsin {league_name} ennustust...", parse_mode=ParseMode.HTML)

    standings = get_standings(league_code)
    standings_text = ""
    if standings:
        for i, t in enumerate(standings[:16], 1):
            standings_text += f"{i}. {t['team']} — {t['points']} punkti\n"

    question = (
        f"Ennusta {league_name} turniiri. "
        f"{'Praegune seis: ' + standings_text if standings_text else 'Turniir pole veel alanud.'}\n"
        f"Anna: kes võidab, TOP 3, üllatus-tiim, pettumus, parim mängija."
    )
    prediction = answer_football_question(question)

    msg = (
        f"╔══════════════════════════════════╗\n"
        f"║  🎯 TURNIIRI ENNUSTUS             ║\n"
        f"╚══════════════════════════════════╝\n"
        f"{league_name}\n\n"
        f"{prediction}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚠️ AI ennustus. Jalgpall on ettearvamatu!</i>"
    )

    if len(msg) > 4000:
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i:i+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_liigad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "╔══════════════════════════════════╗\n"
        "║  📋 TOETATUD LIIGAD              ║\n"
        "╚══════════════════════════════════╝\n\n"
        "<b>Rahvusvahelised:</b>\n"
        "  <code>MM</code> / <code>WC</code> — FIFA MM 🌍\n"
        "  <code>EM</code> / <code>EURO</code> — Euroopa Meistrivõistlused 🇪🇺\n"
        "  <code>NL</code> — Rahvuste Liiga 🏆\n"
        "  <code>CL</code> — Meistrite Liiga ⭐\n"
        "  <code>EL</code> — Euroopa Liiga 🟠\n\n"
        "<b>Riikide liigad:</b>\n"
        "  <code>PL</code> — Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿\n"
        "  <code>BUNDES</code> — Bundesliga 🇩🇪\n"
        "  <code>LALIGA</code> — La Liga 🇪🇸\n"
        "  <code>SERIEA</code> — Serie A 🇮🇹\n"
        "  <code>LIGUE1</code> — Ligue 1 🇫🇷\n"
        "  <code>EREDIVISIE</code> — Eredivisie 🇳🇱\n\n"
        "<b>Näited:</b>\n"
        "  /skanni PL\n"
        "  /mangud CL\n"
        "  /seis LALIGA\n"
        "  /ennusta Arsenal vs Chelsea PL",
        parse_mode=ParseMode.HTML
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if " vs " in text.lower():
        parts = text.lower().split(" vs ")
        home = parts[0].strip().title()
        away = parts[1].strip().split()[0].title()
        league_code = find_league(text)

        await update.message.reply_text(
            f"🔄 <b>Analüüsin: {home} vs {away}</b>\n📡 Laen andmeid...",
            parse_mode=ParseMode.HTML
        )
        result = predict_match_full(home, away, league_code)
        msg = format_full_prediction(result)
        if len(msg) > 4000:
            for i in range(0, len(msg), 4000):
                await update.message.reply_text(msg[i:i+4000], parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return

    await update.message.reply_text("⚽ <b>Otsin vastust...</b>", parse_mode=ParseMode.HTML)
    answer = answer_football_question(text)
    msg = (
        f"╔══════════════════════════════════╗\n"
        f"║  🤖 AI ANALÜÜS                   ║\n"
        f"╚══════════════════════════════════╝\n\n"
        f"{answer}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Käsud: /ennusta · /skanni · /mangud · /seis · /turniir</i>"
    )
    if len(msg) > 4000:
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i:i+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_mm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /mm — Skannib kõik tänased FIFA MM 2026 mängud ja ennustab täielikult.
    Ühe käsuga: mängud + odds + uudised + mängijad + AI ennustus.
    """
    today     = datetime.now().strftime("%d.%m.%Y")
    weekday   = ["Esmaspäev","Teisipäev","Kolmapäev","Neljapäev","Reede","Laupäev","Pühapäev"][datetime.now().weekday()]

    await update.message.reply_text(
        f"🌍 <b>FIFA MM 2026 — PÄEVA ENNUSTUSED</b>\n"
        f"📅 {weekday}, {today}\n\n"
        f"⏳ Skanin tänaseid mänge...\n"
        f"📡 Laen: ESPN mängud · Odds · Uudised · Mängijate andmed · AI analüüs\n\n"
        f"<i>See võtab ~1 minut. Tulemused tulevad kohe...</i>",
        parse_mode=ParseMode.HTML
    )

    # 1. Tänased MM mängud ESPN-ist
    matches = get_today_matches("fifa.world")

    # 2. Kui täna pole, võta järgmised tulevad
    fallback = False
    if not matches:
        matches = get_upcoming_matches("fifa.world", limit=6)
        fallback = True

    if not matches:
        # Viimane võimalus — küsi AI-lt üldine MM ülevaade
        await update.message.reply_text(
            "⚠️ <b>ESPN ei leidnud täna MM mänge.</b>\n\nKüsin AI-lt MM 2026 ülevaadet...",
            parse_mode=ParseMode.HTML
        )
        overview = answer_football_question(
            "Anna täielik ülevaade FIFA MM 2026 hetkeseisust: "
            "kes on grupifaasist edasi pääsenud, kes on välja langenud, "
            "millised on järgmised olulised mängud, kes on favoriidid, "
            "parimad mängijad turniiri senine käik. Ole väga põhjalik."
        )
        standings = get_standings("fifa.world")
        seis_msg = format_standings(standings, "🌍 FIFA MM 2026") if standings else ""

        mm_header = (
            f"╔══════════════════════════════════╗\n"
            f"║  🌍 FIFA MM 2026 — ÜLEVAADE      ║\n"
            f"╚══════════════════════════════════╝\n"
            f"📅 {today}\n\n"
            f"{overview}"
        )
        for chunk in [mm_header[i:i+4000] for i in range(0, len(mm_header), 4000)]:
            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
        if seis_msg:
            for chunk in [seis_msg[i:i+4000] for i in range(0, len(seis_msg), 4000)]:
                await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
        return

    note = "📌 <i>Täna pole mänge — ennustan järgmisi tulevaid mänge.</i>\n\n" if fallback else ""

    # 3. Saada üldine päise sõnum
    await update.message.reply_text(
        f"╔══════════════════════════════════╗\n"
        f"║  🌍 FIFA MM 2026 — {today}  ║\n"
        f"╚══════════════════════════════════╝\n"
        f"{note}"
        f"✅ Leitud <b>{len(matches)} mängu</b>. Alustan põhjalikku analüüsi...\n\n"
        f"<i>Iga mängu jaoks: bookmaker odds · meeskonna uudised · mängijate andmed · AI ennustus</i>",
        parse_mode=ParseMode.HTML
    )

    # 4. Ennusta iga mäng eraldi — täielik analüüs
    for i, m in enumerate(matches, 1):
        home  = m["home"]
        away  = m["away"]
        date  = m.get("date", "")
        venue = m.get("venue", "")

        await update.message.reply_text(
            f"🔄 <b>Analüüsin mäng {i}/{len(matches)}: {home} vs {away}</b>",
            parse_mode=ParseMode.HTML
        )

        result = predict_match_full(home, away, "fifa.world")
        odds   = result.get("odds", {})
        hn     = result.get("home_news", [])
        an     = result.get("away_news", [])
        hs     = result.get("home_stats", {})
        as_    = result.get("away_stats", {})
        pred   = result.get("prediction", "")

        # ── Päis ──
        msg = (
            f"╔══════════════════════════════════╗\n"
            f"║  ⚽ MÄNG {i}/{len(matches)} — MM 2026           ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"🏠 <b>{home}</b>\n"
            f"        🆚\n"
            f"✈️ <b>{away}</b>\n"
        )
        if date:
            msg += f"🕐 <b>{date}</b>"
        if venue:
            msg += f"  📍 {venue}"
        msg += "\n\n"

        # ── Odds ──
        if odds:
            h_pct = odds.get("implied_home_pct", 0)
            d_pct = odds.get("implied_draw_pct", 0)
            a_pct = odds.get("implied_away_pct", 0)
            trend = odds_arrow(h_pct, a_pct)
            msg += (
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>BOOKMAKER KOEFITSIENDID</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Kodu:  <b>{odds.get('home_odds','?')}</b>  {confidence_bar(h_pct)}\n"
                f"🤝 Viik:  <b>{odds.get('draw_odds','?')}</b>  {confidence_bar(d_pct)}\n"
                f"✈️ Külas: <b>{odds.get('away_odds','?')}</b>  {confidence_bar(a_pct)}\n"
                f"   {trend}\n"
                f"📌 <i>{odds.get('bookmakers','')}</i>\n\n"
            )
        else:
            msg += (
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>BOOKMAKER KOEFITSIENDID</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <i>MM koefitsiendid pole hetkel saadaval (The Odds API)</i>\n\n"
            )

        # ── Meeskondade info ──
        def fmt_stats(name, s):
            if not s:
                return ""
            lines = f"   Vorm: {s.get('form','N/A')}\n"
            if s.get("top_scorers") and s.get("top_scorers") != "N/A":
                lines += f"   Tähed: {s.get('top_scorers','')}\n"
            if s.get("country"):
                lines += f"   Riik: {s.get('country','')}\n"
            return lines

        hs_block = fmt_stats(home, hs)
        as_block = fmt_stats(away, as_)
        if hs_block or as_block:
            msg += (
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 <b>MEESKONDADE ANDMED</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 <b>{home}</b>\n{hs_block}\n"
                f"✈️ <b>{away}</b>\n{as_block}\n"
            )

        # ── Uudised ──
        if hn or an:
            msg += (
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📰 <b>VIIMASED UUDISED</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            )
            if hn:
                msg += f"<b>{home}:</b>\n"
                for n in hn[:2]:
                    msg += f"  • {n['title'][:75]}\n"
                msg += "\n"
            if an:
                msg += f"<b>{away}:</b>\n"
                for n in an[:2]:
                    msg += f"  • {n['title'][:75]}\n"
                msg += "\n"

        # ── AI ennustus ──
        msg += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <b>AI ENNUSTUS &amp; ANALÜÜS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pred}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>⚠️ Mängi vastutustundlikult.</i>"
        )

        # Saada sõnum (jaga kui liiga pikk)
        for chunk in [msg[j:j+4000] for j in range(0, len(msg), 4000)]:
            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)

    # 5. Lõpus — MM üldine punktiseis
    await update.message.reply_text(
        "🏆 <b>Laen MM 2026 hetkeseisu...</b>",
        parse_mode=ParseMode.HTML
    )
    standings = get_standings("fifa.world")
    if standings:
        seis = format_standings(standings, "🌍 FIFA MM 2026")
        for chunk in [seis[i:i+4000] for i in range(0, len(seis), 4000)]:
            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)

    # 6. Päeva kokkuvõte AI-lt
    match_list = "\n".join([f"- {m['home']} vs {m['away']}" for m in matches])
    summary = answer_football_question(
        f"Anna lühike (max 5 lauset) päeva kokkuvõte ja soovitus. "
        f"Tänased MM 2026 mängud: {match_list}. "
        f"Milline mäng on täna kõige huvitavam/ettearvamatum? Mis on sinu kindlaim ennustus?"
    )
    await update.message.reply_text(
        f"╔══════════════════════════════════╗\n"
        f"║  💡 PÄEVA KOKKUVÕTE              ║\n"
        f"╚══════════════════════════════════╝\n\n"
        f"{summary}\n\n"
        f"<i>Kasuta /mm igal päeval MM ennustuste jaoks!</i>",
        parse_mode=ParseMode.HTML
    )


# ══════════════════════════════════════════════════════════════
# KÄIVITAMINE
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("⚽ Jalgpalli ennustus bot PRO käivitub...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("mm",      cmd_mm))
    app.add_handler(CommandHandler("ennusta", cmd_ennusta))
    app.add_handler(CommandHandler("skanni",  cmd_skanni))
    app.add_handler(CommandHandler("mangud",  cmd_mangud))
    app.add_handler(CommandHandler("seis",    cmd_seis))
    app.add_handler(CommandHandler("turniir", cmd_turniir))
    app.add_handler(CommandHandler("liigad",  cmd_liigad))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot töötab! /mm /ennusta /skanni /mangud /seis /turniir /liigad")
    app.run_polling()
