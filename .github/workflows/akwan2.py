# env:
#           chat: ${{ secrets.CHAT_TOKEN }}
#           sedinam: ${{ secrets.CHAT_TOKEN_ID_SEDINAM }}
#           sanbenito: ${{ secrets.CHAT_TOKEN_ID_SANBENITO }}
#           wenow_url : ${{ secrets.CHAT_TOKEN_URL }}
#         run: python sika_script.py

 
# d = 0 - today, d = 1 - tomorrow, d = 2, day after tomorrow
# s 1 all games, s2 = live, s3 = finished, s5 = odds added

import os
import time
from datetime import datetime, timedelta
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

token = os.environ.get("chat")
sedinam = os.environ.get("sedinam")
sanbenito = os.environ.get("sanbenito")
pattern_url = os.environ.get("akwan_url")


SCAN_INTERVALS = {
    "late_night":  60,   # 00:00-06:00 → scan every 60 minutes
    "morning":     30,   # 06:00-12:00 → scan every 30 minutes
    "afternoon":   20,   # 12:00-18:00 → scan every 20 minutes
    "evening":     10,   # 18:00-24:00 → scan every 10 minutes
}

PEAK_HOUR_START = 20    # 20:00 — single most productive hour
PEAK_HOUR_END   = 21    # 21:00
PEAK_INTERVAL   = 5     # scan every 5 minutes during peak hour

# ── Day + Time scheduling advice ─────────────────────────────────
# Based on historical pattern: when arbs were discovered by day+hour
DAY_PEAK_HOURS = {
    "sunday":    [(20, "9 PM"),  (2,  "2 AM"),  (21, "9:30 PM")],
    "monday":    [(19, "7 PM"),  (8,  "8 AM"),  (23, "11 PM")],
    "tuesday":   [(14, "2 PM"),  (23, "11 PM"), (7,  "7 AM")],
    "wednesday": [(20, "8 PM"),  (2,  "2 AM"),  (5,  "5 AM")],
    "thursday":  [(11, "11 AM"), (14, "2 PM"),  (23, "11 PM")],
    "friday":    [(15, "3 PM"),  (18, "6 PM"),  (13, "1 PM")],
    "saturday":  [(18, "6 PM"),  (20, "8 PM"),  (7,  "7 AM")],
}

GRADE_A_LEAGUES = {
    "malaysia m3 league",
    "belarus cup",
    "belarus vysshaya",
    "belarus",
    "sweden men",
    "sweden",
    "australia utr pro tennis series",
    "australia",
    "indonesia",
    "ukraine setka cup",
    "usa wta",
    "usa open",
    "sri lanka",
    "beker netherlands",
    "usa utr pro tennis series",
    "usa utr pro tennis series women",
    "oman",
    "mexico atp",
    "finland",
    "czech republic",
    "venezuela segunda division",
    "turkey",
    "vietnam open",
    "bundesliga",
    "kazakhstan championship",
    "usa nba",
    "egypt",
    "malaysia itf",
    "greece a1 women",
    "south korea",
    "portugal",
    "nigeria",
    "nepal prime minister cup",
    "india",
    "malaysia a1",
    "india maharashtra champions trophy",
    "india premier league",
    "usa echl",
    "usa nhl",
    "usa ncaa",
    "india itf",
    "turkey itf",
    "france itf",
    "mexico itf",
    "qatar",
    "turkey bsl men",
    "turkey tb2l",
    "turkey tbl",
    "finland division 1 women",
    "finland divisioona a",
    "vietnam v-league",
    "thailand league i",
    "thailand fa cup",
    "thailand league iii",
    "indonesia championship",
    "scotland women championship",
    "ukraine setka",
    "oman d20",
    "sri lanka mca",
    "india cricket",
    "futsalliga czech",
    "qatar volleyball",
    "turkey tkbl",
    "finland div",
    "malaysia itf",
    "portugal honora",
    "belgium u-21",
    "egypt super cup",
}

TOP_TIER_LEAGUES = {
    "champions league",
    "premier league",
    "la liga",
    "serie a",
    "bundesliga",
    "ligue 1",
    "eredivisie",
    "nba",
    "fifa world cup",
    "world cup",
    "uefa",
    "copa libertadores",
    "efl championship",
    "liga acb",
}

LOWER_TIER_SIGNALS = [
    "2nd", "second", "third", "3rd", "regional",
    "division", "div ", "league 2", "league 3",
    "u19", "u21", "u23", "women", "segunda", "amateur", "youth",
    "cup", "federal", "north", "south", "east", "west",
    "pro league", "first league", "1st league",
]


def normalise_market(raw_market: str) -> str:
    """Map raw betmonitor market label to a normalised gradeable category."""
    m = raw_market.lower().strip()

    if "3-way" in m or "1x2" in m:
        return "football_1x2"
    if "both score" in m or "gg" in m or "bts" in m:
        return "football_bts"
    if "set 1" in m:
        return "tennis_set1"
    if "corners" in m:
        return "corners"
    if "o/u" in m or "over/under" in m:
        return "over_under"
    if "asian handicap" in m or "handicap" in m:
        return "handicap"
    if "cards" in m or "yellow cards" in m:
        return "cards"
    if "penalties" in m:
        return "penalties"
    if "draw no bet" in m:
        return "draw_no_bet"
    if "match winner" in m or "match result" in m or "win" in m or "2-way" in m:
        return "twoway_win"

    return "other"

def normalise_sport(raw_sport: str) -> str:
    """Normalise betmonitor sport label to match grading categories."""
    s = raw_sport.lower().strip()

    if "football" in s:          return "football"
    if "tennis" in s:            return "tennis"
    if "basketball" in s:        return "basketball"
    if "cricket" in s:           return "cricket"
    if "handball" in s:          return "handball"
    if "badminton" in s:         return "badminton"
    if "volleyball" in s:        return "volleyball"
    if "ice hockey" in s:        return "hockey"
    if "hockey" in s:            return "hockey"
    if "table tennis" in s:      return "table_tennis"
    if "futsal" in s:            return "futsal"
    if "american football" in s: return "american_football"
    if "boxing" in s:            return "boxing"

    return "other"

def classify_time(time_str: str) -> str:
    """Classify HH:MM into a named time window."""
    try:
        hour = int(time_str.split(":")[0])
    except (ValueError, IndexError):
        return "unknown"

    if 0  <= hour < 6:  return "late_night"
    if 6  <= hour < 12: return "morning"
    if 12 <= hour < 18: return "afternoon"
    if 18 <= hour < 24: return "evening"
    return "unknown"


def classify_day(day_str: str) -> str:
    """Normalise betmonitor day label to lowercase weekday."""
    d = day_str.lower().strip()
    if d == "today":
        return datetime.now().strftime("%A").lower()
    if d == "tomorrow":
        return (datetime.now() + timedelta(days=1)).strftime("%A").lower()
    if d == "wed":
        return "wednesday"
    return d


def is_grade_a_league(league: str) -> bool:
    league_lower = league.lower()
    return any(k in league_lower for k in GRADE_A_LEAGUES)


def is_top_tier_league(league: str) -> bool:
    league_lower = league.lower()
    return any(k in league_lower for k in TOP_TIER_LEAGUES)


def is_lower_tier_league(league: str) -> bool:
    league_lower = league.lower()
    return (
        not is_top_tier_league(league)
        and any(s in league_lower for s in LOWER_TIER_SIGNALS)
    )


def is_too_far(date_str: str, percentage: float) -> bool:
    """Return True if match is too far in the future to bother searching.
       Rule: skip matches more than 4 days away UNLESS arb% >= 17.
    """
    try:
        match_date = datetime.strptime(
            f"{date_str} {datetime.now().year}", "%d %b %Y"
        )
        days_away = (match_date - datetime.now()).days
        if days_away > 4 and percentage < 17:
            return True
        return False
    except Exception:
        # If date parsing fails do not skip the match
        return False


# ══════════════════════════════════════════════════════════════════
#  SCHEDULING ADVICE
# ══════════════════════════════════════════════════════════════════

def get_day_scheduling_advice() -> str:
    """Return scheduling advice based on the current day using
       historical arb discovery patterns.
    """
    today = datetime.now().strftime("%A").lower()
    peaks = DAY_PEAK_HOURS.get(today, [])

    if not peaks:
        return f"No specific pattern data for {today.capitalize()}."

    lines = [f"📅 Today is {today.capitalize()}."]
    lines.append("Best times to search based on historical patterns:")
    for i, (_, label) in enumerate(peaks, 1):
        lines.append(f"  {i}. {label}")
    return "\n".join(lines)


def get_current_scan_interval() -> int:
    """Return how many minutes to wait before next scan
       based on current time of day and historical discovery patterns.
    """
    hour = datetime.now().hour

    # Peak hour override — most productive single hour
    if PEAK_HOUR_START <= hour < PEAK_HOUR_END:
      return PEAK_INTERVAL

    window   = classify_time(f"{hour}:00")
    interval = SCAN_INTERVALS.get(window, 30)
    return interval



def format_top_arbs_message(graded: list[dict], advice: str) -> str:
    """Format top 10 A+/A/B matches into a Telegram message
       including the scheduling advice for the current day.
    """
    # Filter to A+, A, B only then take top 10 by score
    priority = [g for g in graded if g["grade"] in ("A+", "A", "B")][:15]

     # Filter to A+, A, B only, sort by percentage descending, take top 10
    priority = sorted(
        [g for g in graded if g["grade"] in ("A+", "A", "B", "C")],
        key=lambda x: x["percentage"],
        reverse=True
    )[:15]

    if not priority:
        return (
            "📊 <b>ARB GRADING SCAN COMPLETE</b>\n"
            "No Grade A+/A/B matches found.\n\n"
            f"{advice}"
        )

    lines = [
        f"📊 <b>TOP {len(priority)} ARB OPPORTUNITIES</b>",
        f"Scanned: {datetime.now().strftime('%d %b %Y %H:%M')}",
        "",
        advice,
        "",
        "─────────────────────────────",
    ]

    for i, g in enumerate(priority, 1):
        lines.append(f"<b>{i}. {g['team1']} vs {g['team2']}</b>")
        lines.append(f"   Market : {g['market']}")
        lines.append(f"   Odds : {g['Odds']}")
        lines.append(f"   Grade  : {g['grade']} (Score: {g['score']})")
        lines.append(f"   Sport  : {g['sport']}")
        lines.append(f"   League : {g['league']}")
        lines.append(f"   Date   : {g['date']} {g['day']} @ {g['time']}")
        lines.append(f"   Arb %  : {g['percentage']}%")
        #lines.append(f"   Reason  : {g['reasons']}")
        lines.append("")

    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════
#  CORE GRADING FUNCTION
# ══════════════════════════════════════════════════════════════════

def grade_match(
    sport:    str,
    league:   str,
    market:   str,
    day:      str,
    time_str: str,
) -> dict:
    """
    Grade a single betmonitor match using historical pattern analysis.
    Day and time are NOT used for grading — they are used only by
    the scheduler. Returns dict with score, grade (A+/A/B/C) and reasons.
    """
    score   = 0
    reasons = []

    sport_norm  = normalise_sport(sport)
    market_norm = normalise_market(market)

    # ── 1. Sport scoring ──────────────────────────────────────────
    if sport_norm in ("football", "tennis"):
        score += 7
        reasons.append(f"+7 sport: {sport_norm} (60% of all historical hits)")
    elif sport_norm in ("cricket", "handball"):
        score += 5
        reasons.append(f"+5 sport: {sport_norm} (confirmed hit history)")
    elif sport_norm == "basketball":
        score += 3
        reasons.append("+3 sport: basketball (confirmed hit history)")
    elif sport_norm in ("volleyball", "badminton", "hockey"):
        score += 2
        reasons.append(f"+2 sport: {sport_norm} (confirmed hit history)")
    elif sport_norm in ("table_tennis", "futsal", "american_football", "boxing"):
        score += 1
        reasons.append(f"+1 sport: {sport_norm} (limited hit history)")
    else:
        reasons.append(f"+0 sport: {sport_norm} (no confirmed hit history)")

    # ── 2. Market scoring ─────────────────────────────────────────
    if market_norm == "football_bts":
        score += 7
        reasons.append("+7 market: BTS/GG (4 hits in Apr 2026 — active cluster)")
    elif market_norm == "twoway_win":
        score += 7
        reasons.append("+7 market: 2-way outright win (28 confirmed hits)")
    elif market_norm == "football_1x2":
        score += 5
        reasons.append("+5 market: Football 1x2 / 3-Way (9 confirmed hits)")
    elif market_norm == "tennis_set1":
        score += 4
        reasons.append("+4 market: Tennis Set1 2-way (3 hits, cluster pattern)")
    elif market_norm == "over_under":
        score += 2
        reasons.append("+2 market: Over/Under (6 confirmed hits)")
    elif market_norm == "corners":
        score += 1
        reasons.append("+1 market: corners (1 confirmed hit)")
    else:
        reasons.append(f"+0 market: {market_norm} (no confirmed arb history)")

    # ── 3. League scoring ─────────────────────────────────────────
    if is_grade_a_league(league):
        score += 7
        reasons.append(f"+7 league: '{league}' — known repeat-offender")
    elif is_top_tier_league(league):
        score -= 5
        reasons.append(f"-5 league: '{league}' — top tier (efficient pricing)")
    elif is_lower_tier_league(league):
        score += 4
        reasons.append(f"+4 league: '{league}' — lower tier (less efficient)")
    else:
        reasons.append(f"+0 league: '{league}' — unknown tier")

    # ── 4. Active cluster bonus ───────────────────────────────────
    # Football BTS is in its densest ever cluster as of April 2026
    # Remove this block when cluster ends (5+ day gap appears)
    if market_norm == "football_bts":
        score += 3
        reasons.append("+3 cluster: Football BTS active April 2026 cluster bonus")

    # ── 5. Final grade ────────────────────────────────────────────
    if score >= 20:
        grade = "A+"   # exceptional — search immediately
    elif score >= 15:
        grade = "A"    # high priority
    elif score >= 10:
        grade = "B"    # worth searching
    else:
        grade = "C"    # skip

    return {"score": score, "grade": grade, "reasons": reasons}


def grade_custom_match(
    team1:    str,
    team2:    str,
    sport:    str,
    league:   str,
    market:   str,
    day:      str,
    time_str: str,
):
    """Manually grade a single match you provide yourself."""
    result = grade_match(sport, league, market, day, time_str)
    return result



def parse_betmonitor_entries(raw_text: str) -> list[dict]:
    """
    Parse raw betmonitor scraped text into structured entry dicts.
    Each dict: day, date, time, sport, country, league,
               team1, team2, market, percentage
    Matches more than 4 days away are skipped unless arb% >= 17.
    """
    entries = []

    # Split into individual blocks on day name markers
    day_pattern = (
        r'(?=(?:Today|Tomorrow|Monday|Tuesday|Wednesday|Wed|Thursday|'
        r'Friday|Saturday|Sunday)\s)'
    )
    blocks = re.split(day_pattern, raw_text.strip())
    blocks = [b.strip() for b in blocks if b.strip()]

    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 5:
            continue

        try:
            # Line 0: Day
            day = lines[0]

            # Line 1: Date e.g. "05 Apr"
            date = lines[1]

            # Line 2: Time e.g. "13:00"
            time_str = lines[2]

            # Line 3: Sport · Country · League
            sport_line  = lines[3]
            sport_parts = [p.strip() for p in sport_line.split("·")]
            sport   = sport_parts[0] if len(sport_parts) > 0 else ""
            country = sport_parts[1] if len(sport_parts) > 1 else ""
            league  = sport_parts[2] if len(sport_parts) > 2 else ""

            # Line 4: TEAM1 — TEAM2
            teams_line = lines[4]
            if "—" in teams_line:
                parts = teams_line.split("—")
                team1 = parts[0].strip()
                team2 = parts[1].strip()
            else:
                team1 = teams_line
                team2 = ""

            # Line 5: Market type
            market = lines[5] if len(lines) > 5 else ""

            # Line 6: Odds
            other_lines = lines[6:]
            cleaned = []
            for i in other_lines:
                if (not ("+" in i)) and (not ("%" in i)):
                    cleaned.append(i)

            # print(cleaned)

            odds = [i for i, x in enumerate(cleaned) if re.match(r'^\d+\.\d+$', x)]
            for i in range(0, len(odds), 2):
                a, b = float(cleaned[odds[i]]), float(cleaned[odds[i+1]])
                cleaned[odds[i]] = str(max(a, b))
                cleaned[odds[i+1]] = ''
            cleaned = [x for x in cleaned if x != '']
            # print(cleaned)

            label = {
                        "1": "Home", "2": "Away", "X": "Draw",
                        "O": "Over", "U": "Under",
                        "Y": "Yes",  "N": "No"
                    }
            for k,i in enumerate(cleaned):
                if i in label.keys():
                    cleaned[k] = label[i]

            # print(cleaned)

            cleaned = [x.replace('Highest: ', '') for x in cleaned]
            #print(cleaned)
            Odds = [cleaned[:3], cleaned[3:6]]
            # print(cleaned[:3])
            # print(cleaned[3:6])
            last_selection = cleaned[6:]
            if last_selection:
                Odds.append(last_selection)
            print(Odds)
         
            # Percentage — scan from bottom of block
            percentage = 0.0
            for line in reversed(lines):
                pct_match = re.search(r'(\d+\.?\d*)\s*%', line)
                if pct_match:
                    percentage = float(pct_match.group(1))
                    break

            # Skip matches too far in the future
            # (more than 4 days away unless arb% >= 17)
            if is_too_far(date, percentage):
            
                continue

            entries.append({
                "day":        day,
                "date":       date,
                "time":       time_str,
                "sport":      sport,
                "country":    country,
                "league":     league,
                "team1":      team1,
                "team2":      team2,
                "Odds" :      Odds,
                "market":     market,
                "percentage": percentage,
            })

        except Exception as e:
            print(f"[parser] Skipped block: {e}")
            continue

  
    return entries


# ══════════════════════════════════════════════════════════════════
#  GRADE ALL ENTRIES
# ══════════════════════════════════════════════════════════════════

def grade_all_entries(entries: list[dict]) -> list[dict]:
    """Grade all parsed entries.
       Sorted by score first, then arb percentage as tiebreaker.
    """
    graded = []

    for entry in entries:
        result = grade_match(
            sport    = entry["sport"],
            league   = entry["league"],
            market   = entry["market"],
            day      = entry["day"],
            time_str = entry["time"],
        )
        graded_entry = {**entry, **result}
        graded.append(graded_entry)

    # Sort by score first, arb percentage as tiebreaker — highest first
    graded.sort(key=lambda x: (x["score"], x["percentage"]), reverse=True)
    return graded


# ══════════════════════════════════════════════════════════════════
#  SUMMARY PRINTER
# ══════════════════════════════════════════════════════════════════


def get_by_grade(graded: list[dict], grade: str) -> list[dict]:
    """Filter graded matches by grade. e.g. get_by_grade(graded, 'A')"""
    results = [g for g in graded if g["grade"] == grade.upper().strip()]
    for g in results:
        return results





def scrape_betmonitor() -> str:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Required for cloud servers
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Automatically manages the driver version
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=chrome_options
    )
    driver.get(pattern_url)
    time.sleep(1)
    try:
        container = driver.find_element("css selector", ".sort-cont")
        data      = container.text
        print(f"[betmonitor] Scraped {len(data)} characters")
    except Exception as e:
        print(f"[betmonitor] Scrape error: {e}")
        data = ""
    finally:
        driver.quit()

    return data


def send_telegram(message: str):
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    for id in [sanbenito, sedinam]:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for chunk in chunks:
            payload = {"chat_id": id, "text": chunk}
            try:
                response = requests.post(url, data=payload)
                if response.status_code == 200:
                    print("Message sent ✓")
                else:
                    print(f"Failed: {response.text}")
            except Exception as e:
                print(f"Error: {e}")

# ══════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════

def run_grading_pipeline():
    print("[pipeline] Starting grading pipeline...")

    # Step 1: Scrape betmonitor
    raw_text = scrape_betmonitor()

    if not raw_text.strip():
        print("[pipeline] No data scraped. Exiting.")
        return

    # Step 2: Parse raw text into structured entries
    # Far-fetched matches (>4 days, arb% < 17) are filtered here
    entries = parsentries = parse_betmonitor_entries(raw_text)

    if not entries:
        print("[pipeline] No entries parsed. Exiting.")
        return

    # Step 3: Grade all entries instantly, sorted by score + arb%
    graded = grade_all_entries(entries)

    # Step 4: Print full summary to console
    #print_grade_summary(graded)

    # Step 5: Get scheduling advice for today
    advice = get_day_scheduling_advice()

    # Step 6: Send top 10 A+/A/B to Telegram with scheduling advice
    message = format_top_arbs_message(graded, advice)


    send_telegram(message)

    # Step 7: Return graded list for any downstream use
    return graded


run_grading_pipeline()

# Get interval based on current time window
