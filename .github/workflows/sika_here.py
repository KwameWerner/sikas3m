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
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

token = os.environ.get("chat")
sedinam = os.environ.get("sedinam")
sanbenito = os.environ.get("sanbenito")
wenow_url = os.environ.get("wenow_url")


MATCH_RE  = re.compile(r'^(\d{1,2}:\d{2})(?:Cancelled|Postponed)?(.+?)\s+-\s+(.+?)\s+-:-(?:\s+\[\s*([\d.\s|]+)\s*\])?$')
LEAGUE_RE = re.compile(r'^[A-Z][A-Z\s()./-]+:')


def scrape() -> str:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Required for cloud servers
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Automatically manages the driver version
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=chrome_options
    )
    driver.get(wenow_url)
    time.sleep(5)
    data = driver.find_element("css selector", "#score-data").text
    driver.quit()
    return data


def parse(raw: str) -> list[dict]:
    matches, league = [], "Unknown"
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if not re.match(r'^\d', line) and LEAGUE_RE.match(line):
            league = line.replace(" Standings", "").strip()
            continue
        m = MATCH_RE.match(line)
        if not m:
            continue
        odds = [float(x) for x in m.group(4).split("|")] if m.group(4) else []
        matches.append({
            "league"  : league,
            "time"    : m.group(1),
            "home"    : m.group(2).strip(),
            "away"    : m.group(3).strip(),
            "odds"    : odds,
            "min_odd" : min(odds) if odds else None,
            "status"  : "cancelled" if "Cancelled" in line else "postponed" if "Postponed" in line else "ok",
        })
    return matches


def filter_matches(matches: list[dict], threshold: float) -> dict[str, list]:
    grouped = {}
    for m in matches:
        if m["status"] == "ok" and m["min_odd"] and 1.00 <= m["min_odd"] <= threshold:
            grouped.setdefault(m["league"], []).append(m)
    return grouped


def display(grouped: dict, threshold: float) -> str:
    total = sum(len(v) for v in grouped.values())
    lines = [f"\n  Min odd ≤ {threshold:.2f}  |  {total} match(es)  |  {len(grouped)} league(s)\n"]
    for league, ms in grouped.items():
        lines.append(f"  {league}")
        lines.append(f"  {'─' * 56}")
        for m in ms:
            o = m["odds"]
            lines.append(f"  {m['time']}  {m['home']} vs {m['away']}")
            lines.append(f"         1:{o[0]:.2f}  X:{o[1]:.2f}  2:{o[2]:.2f}  ★ min:{m['min_odd']:.2f}")
        lines.append("")
    return "\n".join(lines)




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

ODD_FILTER = 1.10          # ← change this

raw     = scrape()
matches = parse(raw)
grouped = filter_matches(matches, ODD_FILTER)
matches_found = display(grouped, ODD_FILTER)


from datetime import date
today = date.today()


send_telegram(str(today))
time.sleep(1)
send_telegram(matches_found)


