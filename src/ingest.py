import os, json, time
from pathlib import Path
from dotenv import load_dotenv
import httpx
import pandas as pd

load_dotenv()
API_KEY = os.getenv("APIFOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY, "Accept": "application/json"}

DATA_DIR = Path("data"); (DATA_DIR/"raw").mkdir(parents=True, exist_ok=True); (DATA_DIR/"parquet").mkdir(parents=True, exist_ok=True); (DATA_DIR/"csv").mkdir(parents=True, exist_ok=True)

def get(path, params=None):
    r = httpx.get(f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    js = r.json()
    if js.get("errors"):
        # Gør fejl synlige, men lad kaldet returnere så vi kan håndtere dem
        print("⚠️ API errors:", js["errors"])
    return js

def find_superliga_id():
    # Brug robust søgning: search=Superliga
    resp = get("/leagues", params={"search": "Superliga"})
    for item in resp.get("response", []):
        country = (item.get("country") or {}).get("name", "")
        name = (item.get("league") or {}).get("name", "")
        if country.lower() == "denmark":
            return item["league"]["id"], name
    raise SystemExit("Kunne ikke finde dansk Superliga via search=Superliga")

def fetch_fixtures(league_id: int, season: int):
    all_fx = []

    # Første kald UDEN 'page'
    js = get("/fixtures", params={"league": league_id, "season": season})
    if js.get("errors") and "plan" in js["errors"]:
        print(f"🔒 Ingen adgang til sæson {season} på Free plan. Springer over.")
        return []

    all_fx.extend(js.get("response", []))
    paging = js.get("paging", {}) or {}
    current = paging.get("current", 1)
    total = paging.get("total", 1)

    # Efterfølgende kald MED 'page' hvis der faktisk er flere sider
    while current < total:
        current += 1
        js = get("/fixtures", params={"league": league_id, "season": season, "page": current})
        if js.get("errors") and "plan" in js["errors"]:
            print(f"🔒 Ingen adgang til sæson {season} på Free plan (ved page {current}).")
            break
        all_fx.extend(js.get("response", []))
        paging = js.get("paging", {}) or {}
        total = paging.get("total", total)  # opdatér hvis API'et siger noget nyt

    return all_fx

def normalize_fixtures(items):
    rows = []
    for fx in items:
        fixture = fx.get("fixture", {}) or {}
        league = fx.get("league", {}) or {}
        teams = fx.get("teams", {}) or {}
        goals = fx.get("goals", {}) or {}
        score = fx.get("score", {}) or {}

        rows.append({
            "fixture_id": fixture.get("id"),
            "date": fixture.get("date"),
            "status": (fixture.get("status") or {}).get("short"),
            "venue": (fixture.get("venue") or {}).get("name"),
            "league_id": league.get("id"),
            "league": league.get("name"),
            "season": league.get("season"),
            "round": league.get("round"),
            "home_id": (teams.get("home") or {}).get("id"),
            "home": (teams.get("home") or {}).get("name"),
            "away_id": (teams.get("away") or {}).get("id"),
            "away": (teams.get("away") or {}).get("name"),
            "home_goals": goals.get("home"),
            "away_goals": goals.get("away"),
            "fulltime_home": (score.get("fulltime") or {}).get("home"),
            "fulltime_away": (score.get("fulltime") or {}).get("away"),
        })
    return pd.DataFrame(rows)

def main():
    league_id, league_name = find_superliga_id()
    print(f"✅ Superliga: {league_name} (ID={league_id})")

    allowed_seasons = [2021, 2022, 2023]  # free plan iht. din fejlbesked
    combined = []
    for yr in allowed_seasons:
        print(f"➡️ Henter fixtures for sæson {yr} ...")
        fx = fetch_fixtures(league_id, yr)
        if not fx:
            continue

        # Gem rå NDJSON pr. år
        raw_path = DATA_DIR/"raw"/f"fixtures_superliga_{yr}.ndjson"
        with raw_path.open("w", encoding="utf-8") as f:
            for item in fx:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"💾 Rå data: {raw_path} ({len(fx)} records)")

        df_year = normalize_fixtures(fx)
        combined.append(df_year)

        # Gem fladt pr. år
        pq_path = DATA_DIR/"parquet"/f"fixtures_superliga_{yr}.parquet"
        cs_path = DATA_DIR/"csv"/f"fixtures_superliga_{yr}.csv"
        df_year.to_parquet(pq_path, index=False)
        df_year.to_csv(cs_path, index=False)
        print(f"💾 Parquet: {pq_path} | CSV: {cs_path}  ({len(df_year)} rækker)")

    if combined:
        df_all = pd.concat(combined, ignore_index=True)
        pq_all = DATA_DIR/"parquet"/"fixtures_superliga_2021_2023.parquet"
        cs_all = DATA_DIR/"csv"/"fixtures_superliga_2021_2023.csv"
        df_all.to_parquet(pq_all, index=False)
        df_all.to_csv(cs_all, index=False)
        print(f"✅ Samlet dataset gemt: {pq_all} & {cs_all}  (total {len(df_all)} rækker)")
    else:
        print("⚠️ Fandt ingen data i de tilladte sæsoner. Tjek plan/headers/base-URL.")

if __name__ == "__main__":
    main()
gjej