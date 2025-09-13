from __future__ import annotations
import os, json, sys, httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("APIFOOTBALL_KEY")
if not API_KEY:
    print("❌ APIFOOTBALL_KEY mangler i .env")
    sys.exit(1)

BASE_URL = os.getenv("APIFOOTBALL_BASE", "https://v3.football.api-sports.io")
HEADERS = {"x-apisports-key": API_KEY, "Accept": "application/json"}

DATA_DIR = Path("data"); (DATA_DIR/"reports").mkdir(parents=True, exist_ok=True)
REPORT_PATH = DATA_DIR/"reports"/"apifootball_feature_report.json"

def get(path, params=None):
    r = httpx.get(f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=30)
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        return {"error_http": str(e), "status_code": r.status_code, "text": r.text[:500]}
    js = r.json()
    if js.get("errors"):
        js["_errors"] = js["errors"]  # gør dem lettere at se
    return js

def find_superliga_id():
    js = get("/leagues", params={"search": "Superliga"})
    for item in js.get("response", []):
        if (item.get("country") or {}).get("name", "").lower() == "denmark":
            return item["league"]["id"]
    return None

def pick_sample_fixture(league_id: int, season: int):
    """Find en afsluttet kamp (FT) vi kan bruge til events/lineups/statistics/odds."""
    js = get("/fixtures", params={"league": league_id, "season": season})
    for fx in js.get("response", []):
        stat = (fx.get("fixture", {}).get("status") or {}).get("short")
        if stat == "FT":
            fid = fx["fixture"]["id"]
            home = fx["teams"]["home"]["id"]; away = fx["teams"]["away"]["id"]
            return {"fixture_id": fid, "home_id": home, "away_id": away}
    return None

def status_of(js):
    if isinstance(js, dict) and js.get("_errors"):
        # typisk: {'plan': '...'} eller andet
        return "NO_ACCESS", js.get("_errors")
    if isinstance(js, dict) and js.get("error_http"):
        return "HTTP_ERR", js.get("status_code")
    if len(js.get("response", [])) > 0:
        return "OK", len(js["response"])
    return "EMPTY", 0

def main():
    report = {"base_url": BASE_URL, "probed": []}

    lid = find_superliga_id()
    if not lid:
        print("❌ Kunne ikke finde Superliga via search=Superliga")
        sys.exit(2)
    print(f"✅ Superliga ID: {lid}")

    # Brug tilladt sæson på Free-plan (typisk 2021–2023). Vi prøver 2023 først.
    sample = None
    for yr in (2023, 2022, 2021):
        sample = pick_sample_fixture(lid, yr)
        if sample: 
            sample["season"] = yr
            break

    if not sample:
        print("⚠️ Fandt ingen afsluttet kamp i 2021–2023 (rate limit/plan?). Afbryder.")
        sys.exit(3)

    print(f"🔎 Bruger fixture {sample['fixture_id']} (season {sample['season']}) som prøve")

    # --- Liste over endpoints at teste (minimale parametre) ---
    checks = [
        ("countries", "/countries", {}),
        ("seasons",   "/leagues/seasons", {}),
        ("leagues(DK,2023)", "/leagues", {"country":"Denmark","season":sample["season"]}),
        ("standings", "/standings", {"league": lid, "season": sample["season"]}),
        ("teams",     "/teams", {"league": lid, "season": sample["season"]}),
        ("fixtures",  "/fixtures", {"league": lid, "season": sample["season"]}),
        ("h2h",       "/fixtures/headtohead", {"h2h": f"{sample['home_id']}-{sample['away_id']}"}),
        ("events",    "/fixtures/events", {"fixture": sample["fixture_id"]}),
        ("lineups",   "/fixtures/lineups", {"fixture": sample["fixture_id"]}),
        ("stats_teams","/fixtures/statistics", {"fixture": sample["fixture_id"]}),
        ("stats_players","/fixtures/players", {"fixture": sample["fixture_id"]}),
        ("topscorers","/players/topscorers", {"league": lid, "season": sample["season"]}),
        ("coaches",   "/coachs", {"team": sample["home_id"]}),  # API staver coachs i v3
        ("transfers", "/transfers", {"team": sample["home_id"]}),
        ("trophies",  "/trophies", {"team": sample["home_id"]}),
        ("sidelined", "/sidelined", {"team": sample["home_id"]}),
        ("injuries",  "/injuries", {"league": lid, "season": sample["season"]}),
        ("odds_prematch","/odds", {"fixture": sample["fixture_id"]}),
        ("odds_inplay",  "/odds/live", {}),  # kan ofte være tomt uden live kampe
        ("predictions","/predictions", {"fixture": sample["fixture_id"]}),
        ("statistics_league","/leagues", {"id": lid}),
    ]

    for name, path, params in checks:
        js = get(path, params=params)
        st, meta = status_of(js)
        print(f"{name:<18} -> {st} {meta}")
        report["probed"].append({
            "endpoint": name,
            "path": path,
            "params": params,
            "status": st,
            "meta": meta
        })

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📝 Rapport gemt: {REPORT_PATH}")

if __name__ == "__main__":
    main()
