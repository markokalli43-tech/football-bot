#!/usr/bin/env python3
"""
Jalgpalli Ennustus Telegram Bot — PRO VERSIOON
Odds + Uudised + Mängijate andmed + MM 2026 automaatne skannimine
"""

import requests
from datetime import datetime, timezone, timedelta
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

TELEGRAM_BOT_TOKEN = "8808987324:AAHHd0PhZQG4C0Wa_BG76dGoTLjLjlhlLws"
GROQ_API_KEY       = "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"
ODDS_API_KEY       = "b88ee2f550d84d79cb66c1c45e0843ea"
NEWS_API_KEY       = "daa69dc1b60541fdb5d24458eabbc3ae"
API_FOOTBALL_KEY   = "0bdce33132mshe8ef5e7f6499c67p1ecf3bjsn21627e33ef2b"

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
    "fifa.world": "🌍 FIFA MM 2026",
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


# ══════════════════════════════════════════════════════════════
# ESPN — MÄNGUD JA SEIS
# ══════════════════════════════════════════════════════════════

def find_league(text):
    text_up = text.upper()
    for key, code in LEAGUES.items():
        if key in text_up:
            return code
    return "fifa.world"


def _parse_matches(events):
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
            "date": date_fmt,
            "score_home": home.get("score", "-"),
            "score_away": away.get("score", "-"),
            "completed": status.get("completed", False),
            "in_progress": status.get("name", "") == "STATUS_IN_PROGRESS",
            "venue": comp.get("venue", {}).get("fullName", ""),
        })
    return matches


def get_today_matches(league_code):
    try:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        r = requests.get(f"{ESPN_BASE}/{league_code}/scoreboard?dates={today}", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        return _parse_matches(r.json().get("events", []))
    except Exception:
        return []


def get_upcoming_matches(league_code, limit=8):
    try:
        r = requests.get(f"{ESPN_BASE}/{league_code}/scoreboard", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        return _parse_matches(r.json().get("events", [])[:limit])
    except Exception:
        return []


def get_standings(league_code):
    try:
        r = requests.get(f"{ESPN_V2}/{league_code}/standings", headers=HEADERS, timeout=10)
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
                    "group": group_name,
                    "played":  stats.get("gamesPlayed", stats.get("played", 0)),
                    "wins":    stats.get("wins", 0),
                    "draws":   stats.get("ties", stats.get("draws", 0)),
                    "losses":  stats.get("losses", 0),
                    "gd":      stats.get("pointDifferential", stats.get("goalDifference", 0)),
                    "points":  stats.get("points", 0),
                })
        return standings
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# THE ODDS API
# ══════════════════════════════════════════════════════════════

def get_odds(home, away, league_code=""):
    sport = ODDS_SPORTS.get(league_code, "soccer_epl")
    try:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
            params={"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"},
            timeout=10
        )
        if r.status_code != 200:
            return {}
        home_l = home.lower()
        for event in r.json():
            ht = event.get("home_team", "").lower()
            if any(w in ht for w in home_l.split() if len(w) > 3) or any(w in home_l for w in ht.split() if len(w) > 3):
                bookmakers = event.get("bookmakers", [])
                if not bookmakers:
                    continue
                home_p, draw_p, away_p, names = [], [], [], []
                for bk in bookmakers[:6]:
                    names.append(bk.get("title", ""))
                    for mkt in bk.get("markets", []):
                        if mkt.get("key") == "h2h":
                            for oc in mkt.get("outcomes", []):
                                nm = oc.get("name", "").lower()
                                pr = oc.get("price", 0)
                                if any(w in nm for w in ht.split() if len(w) > 3):
                                    home_p.append(pr)
                                elif "draw" in nm:
                                    draw_p.append(pr)
                                else:
                                    away_p.append(pr)
                if home_p and away_p:
                    ah = round(sum(home_p)/len(home_p), 2)
                    ad = round(sum(draw_p)/len(draw_p), 2) if draw_p else 0
                    aa = round(sum(away_p)/len(away_p), 2)
                    total = (1/ah) + (1/ad if ad else 0) + (1/aa)
                    return {
                        "home_odds": ah, "draw_odds": ad, "away_odds": aa,
                        "bookmakers": ", ".join(names[:4]),
                        "implied_home_pct": round((1/ah)/total*100, 1),
                        "implied_draw_pct": round((1/ad)/total*100, 1) if ad else 0,
                        "implied_away_pct": round((1/aa)/total*100, 1),
                    }
    except Exception:
        pass
    return {}


# ══════════════════════════════════════════════════════════════
# NEWS API
# ══════════════════════════════════════════════════════════════

def get_team_news(team, days_back=7):
    try:
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": f"{team} football soccer", "from": from_date,
                    "sortBy": "publishedAt", "language": "en",
                    "pageSize": 5, "apiKey": NEWS_API_KEY},
            timeout=8
        )
        if r.status_code != 200:
            return []
        return [{"title": a.get("title",""), "date": a.get("publishedAt","")[:10]}
                for a in r.json().get("articles", []) if a.get("title")]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# RAPIDAPI — MEESKONNA ANDMED
# ══════════════════════════════════════════════════════════════

def get_team_stats(team_name, league_code="eng.1"):
    headers = {
        "X-RapidAPI-Key": API_FOOTBALL_KEY,
        "X-RapidAPI-Host": "free-api-live-football-data.p.rapidapi.com",
    }
    try:
        r = requests.get(
            "https://free-api-live-football-data.p.rapidapi.com/football-search-teams",
            params={"term": team_name}, headers=headers, timeout=8
        )
        if r.status_code != 200:
            return {}
        teams = r.json().get("response", {}).get("teams", [])
        if not teams:
            return {}
        team = teams[0]
        team_id = team.get("id")
        rp = requests.get(
            "https://free-api-live-football-data.p.rapidapi.com/football-get-team-players",
            params={"teamid": team_id}, headers=headers, timeout=8
        )
        players = rp.json().get("response", {}).get("players", []) if rp.status_code == 200 else []
        attackers = [p for p in players if p.get("position","").upper() in ["ATTACKER","FORWARD","STRIKER"]][:3]
        top = ", ".join([p.get("name","") for p in attackers]) if attackers else "N/A"
        return {
            "team": team.get("name", team_name),
            "country": team.get("country", ""),
            "top_scorers": top,
        }
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════
# GROQ AI ENNUSTUS
# ══════════════════════════════════════════════════════════════

def predict_match_full(home, away, league_code=""):
    result = {"home": home, "away": away, "odds": {}, "home_news": [], "away_news": [], "home_stats": {}, "away_stats": {}, "prediction": ""}
    result["odds"]       = get_odds(home, away, league_code)
    result["home_news"]  = get_team_news(home)
    result["away_news"]  = get_team_news(away)
    result["home_stats"] = get_team_stats(home, league_code)
    result["away_stats"] = get_team_stats(away, league_code)

    o = result["odds"]
    odds_text = (
        f"KOEFITSIENDID: {home} {o.get('home_odds','N/A')} ({o.get('implied_home_pct','?')}%) | "
        f"Viik {o.get('draw_odds','N/A')} ({o.get('implied_draw_pct','?')}%) | "
        f"{away} {o.get('away_odds','N/A')} ({o.get('implied_away_pct','?')}%)"
    ) if o else "Koefitsiendid pole saadaval"

    def news_txt(name, arts):
        return "\n".join([f"  • [{a['date']}] {a['title']}" for a in arts[:3]]) if arts else "  Uudiseid pole"

    context = f"""MÄNG: {home} vs {away}
{odds_text}
{home} uudised:\n{news_txt(home, result['home_news'])}
{away} uudised:\n{news_txt(away, result['away_news'])}
{home} mängijad: {result['home_stats'].get('top_scorers','N/A')}
{away} mängijad: {result['away_stats'].get('top_scorers','N/A')}"""

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Sa oled maailma parim jalgpallianalüütik. Kasuta kõiki andmeid. Vasta EESTI KEELES. Ole täpne ja struktureeritud."},
                {"role": "user", "content": f"""{context}

Anna ennustus EESTI KEELES:

🔍 VORMIANALÜÜS
[mõlema meeskonna hetkeolukord uudiste põhjal]

⚖️ KOEFITSIENTIDE ANALÜÜS
[mida bookmaker'id ütlevad, kus on väärtus]

🎯 ENNUSTUS
Tulemus: [KODU VÕIT / VIIK / KÜLAS VÕIT]
Ennustatav skoor: X:X
Kindlustase: [KÕRGE / KESKMINE / MADAL]

📈 TÕENÄOSUSED
Kodu: X% | Viik: X% | Külas: X%

💡 PÕHJENDUS
[2-3 peamist põhjust]

⚠️ RISKID
[mis võiks ennustuse ümber lükata]"""}
            ],
            max_tokens=1000,
        )
        result["prediction"] = resp.choices[0].message.content
    except Exception as e:
        result["prediction"] = f"❌ AI viga: {e}"
    return result


def answer_football_question(question):
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Sa oled maailma parim jalgpallianalüütik. Vasta EESTI KEELES. Ole täpne ja põhjalik."},
                {"role": "user", "content": question}
            ],
            max_tokens=1000,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"❌ Viga: {e}"


# ══════════════════════════════════════════════════════════════
# VORMISTUS
# ══════════════════════════════════════════════════════════════

def confidence_bar(pct):
    filled = int(float(pct) / 10)
    return "█" * filled + "░" * (10 - filled) + f" {pct}%"

def odds_arrow(h, a):
    h, a = float(h or 0), float(a or 0)
    if h > a + 15: return "⬅️ kodu tugevalt favoriit"
    elif h > a + 5: return "◀️ kodu favoriit"
    elif a > h + 15: return "➡️ külas tugevalt favoriit"
    elif a > h + 5: return "▶️ külas favoriit"
    return "↔️ tasavägine mäng"

def format_standings(standings, league_name):
    if not standings:
        return "❌ Seisu ei leitud."
    msg = f"╔══════════════════════════════════╗\n║  🏆 PUNKTISEIS                    ║\n╚══════════════════════════════════╝\n{league_name}\n\n"
    current_group = None
    for i, t in enumerate(standings[:32], 1):
        if t.get("group") and t["group"] != current_group:
            current_group = t["group"]
            msg += f"\n<b>📌 {current_group}</b>\n"
            msg += "<code> #  Meeskond           M  V  Vi K  GD  Pts</code>\n"
        gd = str(t['gd'])
        if str(t['gd']).lstrip('-').replace('.','').isdigit() and float(str(t['gd'])) > 0:
            gd = f"+{t['gd']}"
        msg += f"<code>{str(i)+'.':<3} {t['team'][:18]:<18} {str(t['played']):>2} {str(t['wins']):>2} {str(t['draws']):>2} {str(t['losses']):>2} {gd:>4} {str(t['points']):>4}</code>\n"
    msg += "\n<i>M=Mängud V=Võidud Vi=Viigid K=Kaotused GD=Väravad Pts=Punktid</i>"
    return msg


# ══════════════════════════════════════════════════════════════
# TELEGRAM KÄSUD
# ══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ <b>JALGPALLI ENNUSTUS BOT — PRO</b>\n\n"
        "Kasutan <b>ESPN + The Odds API + NewsAPI + Groq AI</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌍 <b>/mm</b> — MM 2026 tänaste mängude täisennustus\n\n"
        "🔮 <b>/ennusta</b> Brasiilia vs Argentina\n"
        "📅 <b>/mangud</b> [liiga] — järgmised mängud\n"
        "🏆 <b>/seis</b> [liiga] — punktitabel\n"
        "🎯 <b>/turniir</b> [liiga] — turniiri ennustus\n"
        "📋 <b>/liigad</b> — kõik toetatud liigad\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Kirjuta ka lihtsalt küsimus: <i>Kes võidab MM 2026?</i>\n\n"
        "⚠️ <i>Mängi vastutustundlikult.</i>",
        parse_mode=ParseMode.HTML
    )


async def cmd_mm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today   = datetime.now().strftime("%d.%m.%Y")
    weekday = ["Esmaspäev","Teisipäev","Kolmapäev","Neljapäev","Reede","Laupäev","Pühapäev"][datetime.now().weekday()]

    await update.message.reply_text(
        f"🌍 <b>FIFA MM 2026 — PÄEVA ENNUSTUSED</b>\n"
        f"📅 {weekday}, {today}\n\n"
        f"⏳ Skanin mänge, odds, uudised, AI analüüs...\n"
        f"<i>Võtab ~1 minut.</i>",
        parse_mode=ParseMode.HTML
    )

    matches = get_today_matches("fifa.world")
    fallback = False
    if not matches:
        matches = get_upcoming_matches("fifa.world", limit=6)
        fallback = True

    if not matches:
        overview = answer_football_question(
            "Anna täielik ülevaade FIFA MM 2026 hetkeseisust eesti keeles: "
            "kes on edasi pääsenud, kes välja langenud, järgmised olulised mängud, favoriidid, parimad mängijad."
        )
        standings = get_standings("fifa.world")
        await update.message.reply_text(
            f"╔══════════════════════════════════╗\n"
            f"║  🌍 FIFA MM 2026 — ÜLEVAADE      ║\n"
            f"╚══════════════════════════════════╝\n\n{overview}",
            parse_mode=ParseMode.HTML
        )
        if standings:
            seis = format_standings(standings, "🌍 FIFA MM 2026")
            for chunk in [seis[i:i+4000] for i in range(0, len(seis), 4000)]:
                await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
        return

    note = "📌 <i>Täna pole mänge — ennustan järgmisi mänge.</i>\n\n" if fallback else ""
    await update.message.reply_text(
        f"╔══════════════════════════════════╗\n"
        f"║  🌍 FIFA MM 2026 — {today}  ║\n"
        f"╚══════════════════════════════════╝\n"
        f"{note}✅ Leitud <b>{len(matches)} mängu</b>. Analüüsin...",
        parse_mode=ParseMode.HTML
    )

    for i, m in enumerate(matches, 1):
        home, away = m["home"], m["away"]
        await update.message.reply_text(
            f"🔄 <b>Mäng {i}/{len(matches)}: {home} vs {away}</b>",
            parse_mode=ParseMode.HTML
        )
        r   = predict_match_full(home, away, "fifa.world")
        odds = r.get("odds", {})
        hn   = r.get("home_news", [])
        an   = r.get("away_news", [])
        pred = r.get("prediction", "")

        msg = (
            f"╔══════════════════════════════════╗\n"
            f"║  ⚽ MÄNG {i}/{len(matches)} — MM 2026           ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"🏠 <b>{home}</b>\n        🆚\n✈️ <b>{away}</b>\n"
        )
        if m.get("date"): msg += f"🕐 <b>{m['date']}</b>"
        if m.get("venue"): msg += f"  📍 {m['venue']}"
        msg += "\n\n"

        if odds:
            hp = odds.get("implied_home_pct", 0)
            dp = odds.get("implied_draw_pct", 0)
            ap = odds.get("implied_away_pct", 0)
            msg += (
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>BOOKMAKER KOEFITSIENDID</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 <b>{home}:</b>  <b>{odds.get('home_odds','?')}</b>  {confidence_bar(hp)}\n"
                f"🤝 Viik:  <b>{odds.get('draw_odds','?')}</b>  {confidence_bar(dp)}\n"
                f"✈️ <b>{away}:</b> <b>{odds.get('away_odds','?')}</b>  {confidence_bar(ap)}\n"
                f"   {odds_arrow(hp, ap)}\n"
                f"📌 <i>{odds.get('bookmakers','')}</i>\n\n"
            )

        if hn or an:
            msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n📰 <b>UUDISED</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            if hn:
                msg += f"<b>{home}:</b>\n" + "\n".join([f"  • {n['title'][:75]}" for n in hn[:2]]) + "\n\n"
            if an:
                msg += f"<b>{away}:</b>\n" + "\n".join([f"  • {n['title'][:75]}" for n in an[:2]]) + "\n\n"

        msg += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <b>AI ENNUSTUS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pred}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>⚠️ Mängi vastutustundlikult.</i>"
        )

        for chunk in [msg[j:j+4000] for j in range(0, len(msg), 4000)]:
            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)

    standings = get_standings("fifa.world")
    if standings:
        seis = format_standings(standings, "🌍 FIFA MM 2026")
        for chunk in [seis[i:i+4000] for i in range(0, len(seis), 4000)]:
            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)

    match_list = ", ".join([f"{m['home']} vs {m['away']}" for m in matches])
    summary = answer_football_question(
        f"Tänased MM 2026 mängud: {match_list}. "
        f"Anna lühike kokkuvõte: milline on täna kindlaim ennustus ja milline kõige ettearvamatum mäng? Max 4 lauset eesti keeles."
    )
    await update.message.reply_text(
        f"╔══════════════════════════════════╗\n"
        f"║  💡 PÄEVA KOKKUVÕTE              ║\n"
        f"╚══════════════════════════════════╝\n\n"
        f"{summary}\n\n"
        f"<i>Kasuta /mm iga päev MM ennustuste jaoks!</i>",
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
        await update.message.reply_text("❌ Kasuta: <b>/ennusta Brasiilia vs Argentina</b>", parse_mode=ParseMode.HTML)
        return

    league_code = find_league(text)
    await update.message.reply_text(f"🔄 <b>Analüüsin: {home} vs {away}</b>\n📡 Laen andmeid...", parse_mode=ParseMode.HTML)
    r = predict_match_full(home, away, league_code)
    odds = r.get("odds", {})
    hn = r.get("home_news", [])
    an = r.get("away_news", [])
    pred = r.get("prediction", "")

    msg = f"╔══════════════════════════════════╗\n║  🔮 MÄNGU ENNUSTUS               ║\n╚══════════════════════════════════╝\n\n🏠 <b>{home}</b>\n        🆚\n✈️ <b>{away}</b>\n\n"

    if odds:
        hp = odds.get("implied_home_pct", 0)
        dp = odds.get("implied_draw_pct", 0)
        ap = odds.get("implied_away_pct", 0)
        msg += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n📊 <b>BOOKMAKER KOEFITSIENDID</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏠 <b>{home}:</b>  <b>{odds.get('home_odds','?')}</b>  {confidence_bar(hp)}\n"
            f"🤝 Viik:  <b>{odds.get('draw_odds','?')}</b>  {confidence_bar(dp)}\n"
            f"✈️ <b>{away}:</b> <b>{odds.get('away_odds','?')}</b>  {confidence_bar(ap)}\n"
            f"   {odds_arrow(hp, ap)}\n📌 <i>{odds.get('bookmakers','')}</i>\n\n"
        )
    if hn or an:
        msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n📰 <b>UUDISED</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        if hn: msg += f"<b>{home}:</b>\n" + "\n".join([f"  • {n['title'][:75]}" for n in hn[:2]]) + "\n\n"
        if an: msg += f"<b>{away}:</b>\n" + "\n".join([f"  • {n['title'][:75]}" for n in an[:2]]) + "\n\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n🤖 <b>AI ENNUSTUS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n{pred}\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n<i>⚠️ Mängi vastutustundlikult.</i>"

    for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)


async def cmd_mangud(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).upper() if context.args else "MM"
    league_code = find_league(text)
    league_name = LEAGUE_NAMES.get(league_code, league_code)
    await update.message.reply_text(f"📅 Laen {league_name} mänge...", parse_mode=ParseMode.HTML)
    matches = get_upcoming_matches(league_code)
    if not matches:
        await update.message.reply_text("❌ Mänge ei leitud. Proovi: /liigad", parse_mode=ParseMode.HTML)
        return
    msg = f"╔══════════════════════════════════╗\n║  📅 JÄRGMISED MÄNGUD              ║\n╚══════════════════════════════════╝\n{league_name}\n\n"
    for m in matches:
        status = f"🔴 <b>LIVE</b> {m['score_home']}:{m['score_away']}" if m["in_progress"] else (f"✅ {m['score_home']}:{m['score_away']}" if m["completed"] else f"🕐 <b>{m['date']}</b>")
        msg += f"🏠 <b>{m['home']}</b> vs <b>{m['away']}</b> ✈️\n   {status}"
        if m.get("venue"): msg += f" · {m['venue']}"
        msg += "\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n💡 <i>/ennusta [tiim1] vs [tiim2]</i>"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_seis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).upper() if context.args else "MM"
    league_code = find_league(text)
    league_name = LEAGUE_NAMES.get(league_code, league_code)
    await update.message.reply_text(f"🏆 Laen {league_name} seisu...", parse_mode=ParseMode.HTML)
    standings = get_standings(league_code)
    msg = format_standings(standings, league_name)
    for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)


async def cmd_turniir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).upper() if context.args else "MM"
    league_code = find_league(text)
    league_name = LEAGUE_NAMES.get(league_code, league_code)
    await update.message.reply_text(f"🎯 Analüüsin {league_name}...", parse_mode=ParseMode.HTML)
    standings = get_standings(league_code)
    seis_txt = "\n".join([f"{i}. {t['team']} — {t['points']} p" for i, t in enumerate(standings[:16], 1)]) if standings else ""
    question = f"Ennusta {league_name}. {'Seis: ' + seis_txt if seis_txt else 'Turniir pole alanud.'} Kes võidab? TOP 3? Üllatus? Pettumus? Parim mängija?"
    pred = answer_football_question(question)
    msg = f"╔══════════════════════════════════╗\n║  🎯 TURNIIRI ENNUSTUS             ║\n╚══════════════════════════════════╝\n{league_name}\n\n{pred}\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n<i>⚠️ AI ennustus. Jalgpall on ettearvamatu!</i>"
    for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)


async def cmd_liigad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "╔══════════════════════════════════╗\n║  📋 TOETATUD LIIGAD              ║\n╚══════════════════════════════════╝\n\n"
        "<b>Rahvusvahelised:</b>\n"
        "  <code>MM</code> — FIFA MM 2026 🌍\n"
        "  <code>EM</code> / <code>EURO</code> — Euroopa Meistrivõistlused 🇪🇺\n"
        "  <code>CL</code> — Meistrite Liiga ⭐\n"
        "  <code>EL</code> — Euroopa Liiga 🟠\n\n"
        "<b>Riikide liigad:</b>\n"
        "  <code>PL</code> — Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿\n"
        "  <code>BUNDES</code> — Bundesliga 🇩🇪\n"
        "  <code>LALIGA</code> — La Liga 🇪🇸\n"
        "  <code>SERIEA</code> — Serie A 🇮🇹\n"
        "  <code>LIGUE1</code> — Ligue 1 🇫🇷\n\n"
        "<b>Näited:</b>\n  /mm · /seis PL · /turniir CL\n  /ennusta Arsenal vs Chelsea PL",
        parse_mode=ParseMode.HTML
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if " vs " in text.lower():
        parts = text.lower().split(" vs ")
        home = parts[0].strip().title()
        away = parts[1].strip().split()[0].title()
        league_code = find_league(text)
        await update.message.reply_text(f"🔄 <b>Analüüsin: {home} vs {away}</b>\n📡 Laen andmeid...", parse_mode=ParseMode.HTML)
        r = predict_match_full(home, away, league_code)
        odds = r.get("odds", {})
        pred = r.get("prediction", "")
        msg = f"╔══════════════════════════════════╗\n║  🔮 ENNUSTUS                      ║\n╚══════════════════════════════════╝\n\n🏠 <b>{home}</b> 🆚 ✈️ <b>{away}</b>\n\n"
        if odds:
            hp = odds.get("implied_home_pct", 0)
            dp = odds.get("implied_draw_pct", 0)
            ap = odds.get("implied_away_pct", 0)
            msg += f"📊 <b>{home}</b> <b>{odds.get('home_odds','?')}</b> {confidence_bar(hp)}\n🤝 Viik <b>{odds.get('draw_odds','?')}</b> {confidence_bar(dp)}\n✈️ <b>{away}</b> <b>{odds.get('away_odds','?')}</b> {confidence_bar(ap)}\n\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n🤖 <b>AI ENNUSTUS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n{pred}\n\n<i>⚠️ Mängi vastutustundlikult.</i>"
        for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
        return

    await update.message.reply_text("⚽ <b>Otsin vastust...</b>", parse_mode=ParseMode.HTML)
    answer = answer_football_question(text)
    msg = f"╔══════════════════════════════════╗\n║  🤖 AI ANALÜÜS                   ║\n╚══════════════════════════════════╝\n\n{answer}\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Käsud: /mm · /ennusta · /mangud · /seis · /turniir</i>"
    for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════════════════
# KÄIVITAMINE
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("⚽ Jalgpalli ennustus bot PRO käivitub...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("mm",      cmd_mm))
    app.add_handler(CommandHandler("ennusta", cmd_ennusta))
    app.add_handler(CommandHandler("mangud",  cmd_mangud))
    app.add_handler(CommandHandler("seis",    cmd_seis))
    app.add_handler(CommandHandler("turniir", cmd_turniir))
    app.add_handler(CommandHandler("liigad",  cmd_liigad))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot töötab! /mm /ennusta /mangud /seis /turniir /liigad")
    app.run_polling()
