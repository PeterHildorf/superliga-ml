from __future__ import annotations
import os, httpx
from dotenv import load_dotenv
import pandas as pd

# Konfig
SEASON = int(os.getenv("APIFOOTBALL_SEASON", "2025"))  # 2025 = sæson 2025/26 hos API-FOOTBALL
LEAGUE_ID = 119  # Dansk Superliga (fundet tidligere)
BASE = "https://v3.football.api-sports.io"

load_dotenv()
KEY = os.getenv("APIFOOTBALL_KEY")
HDRS = {"x-apisports-key": KEY, "Accept": "application/json"}

def get(path, params=None):
    r = httpx.get(f"{BASE}{path}", params=params, headers=HDRS, timeout=30)
    r.raise_for_status()
    js = r.json()
    if js.get("errors"):
        raise SystemExit(f"API errors: {js['errors']}")
    return js["response"]

def main():
    # Hent ALLE fixtures for sæsonen
    resp = get("/fixtures", {"league": LEAGUE_ID, "season": SEASON})
    if not resp:
        print("Ingen fixtures fundet.")
        return

    # Flad tabel
    rows = []
    for fx in resp:
        fxt = fx["fixture"]; lg = fx["league"]; tm = fx["teams"]; gl = fx["goals"]
        rows.append({
            "fixture_id": fxt["id"],
            "utc": fxt["date"],               # ISO-8601 med +00:00
            "status": fxt["status"]["short"], # NS=not started, FT=finished
            "round": lg.get("round"),
            "home": tm["home"]["name"],
            "away": tm["away"]["name"],
            "hg": gl["home"],
            "ag": gl["away"],
        })
    df = pd.DataFrame(rows)
    # Tidsbehandling
    df["dt_utc"] = pd.to_datetime(df["utc"], utc=True)
    df["dt_dk"] = df["dt_utc"].dt.tz_convert("Europe/Copenhagen")

    # Seneste 10 SPILLEDE (status FT), sorteret efter dansk tid senest først
    last10 = df[df["status"].eq("FT")].sort_values("dt_utc", ascending=False).head(10)

    # Næste 10 PLANLAGTE (status NS), sorteret frem i tid
    next10 = df[df["status"].eq("NS")].sort_values("dt_utc", ascending=True).head(10)

    # Print pænt
    print("\n=== Seneste 10 kampe (spillet) ===")
    for _, r in last10.iterrows():
        print(f"{r['dt_dk']:%d-%m-%Y %H:%M}  {r['home']} {r['hg']}-{r['ag']} {r['away']}  (runde: {r['round']})")

    print("\n=== Næste 10 kampe (planlagt) ===")
    for _, r in next10.iterrows():
        print(f"{r['dt_dk']:%d-%m-%Y %H:%M}  {r['home']} vs {r['away']}  (runde: {r['round']})")

if __name__ == "__main__":
    main()
