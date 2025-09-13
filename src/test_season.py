# src/test_season.py
from dotenv import load_dotenv
import os, httpx, sys

load_dotenv()
KEY = os.getenv("APIFOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"
HDRS = {"x-apisports-key": KEY, "Accept": "application/json"}

SEASON = int(os.getenv("APIFOOTBALL_SEASON", "2025"))  # 2024 = sæson 2024/25
LID = 119  # Superliga-ID (fundet tidligere)

r = httpx.get(f"{BASE}/fixtures", params={"league": LID, "season": SEASON}, headers=HDRS, timeout=30)
r.raise_for_status()
js = r.json()
errs = js.get("errors")
n = len(js.get("response", []))

print("errors:", errs)
print(f"fixtures {SEASON}:", n)
# Print de 5 første for at se det lever:
for fx in js.get("response", [])[:5]:
    date = fx["fixture"]["date"]
    home = fx["teams"]["home"]["name"]
    away = fx["teams"]["away"]["name"]
    stat = fx["fixture"]["status"]["short"]
    print(date, stat, f"{home} vs {away}")
