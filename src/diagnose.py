from __future__ import annotations
import os, sys, json, time, argparse
from pathlib import Path
import httpx
from dotenv import load_dotenv

# ---------- konfiguration ----------
RATE_DELAY = float(os.getenv("APIFOOTBALL_RATE_DELAY", "7.0"))  # sek. mellem kald (Free ~7s)
MAX_RETRIES = 3

# ---------- miljø ----------
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")
API_KEY  = os.getenv("APIFOOTBALL_KEY")
BASE_URL = os.getenv("APIFOOTBALL_BASE", "https://v3.football.api-sports.io")

if not API_KEY:
    print("❌ APIFOOTBALL_KEY mangler i .env i projektroden")
    sys.exit(1)

HEADERS = {
    "x-apisports-key": API_KEY,
    "Accept": "application/json",
}

# ---------- hjælpefunktioner ----------
def throttled_get(path: str, params=None, max_retries: int = MAX_RETRIES) -> dict:
    """GET med simpel throttling + 429-retry."""
    url = f"{BASE_URL}{path}"
    for attempt in range(max_retries + 1):
        r = httpx.get(url, params=params, headers=HEADERS, timeout=30)
        if r.status_code == 429:
            wait = RATE_DELAY * (attempt + 1)
            print(f"⏳ 429 rate limit – venter {wait:.1f}s og prøver igen ...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        js = r.json()
        # lille generel pause for at holde os under 10 rpm
        time.sleep(RATE_DELAY)
        return js
    # hvis vi ender her, lykkedes det ikke
    return {"errors": {"rateLimit": "Too many requests"}}

def status_of(js: dict) -> tuple[str, object]:
    if isinstance(js, dict) and js.get("errors"):
        return "NO_ACCESS", js["errors"]
    resp = js.get("response", [])
    return ("OK", len(resp)) if resp else ("EMPTY", 0)

def find_superliga_id() -> int | None:
    js = throttled_get("/leagues", {"search": "Superliga"})
    for item in js.get("response", []):
        if (item.get("country") or {}).get("name", "").lower() == "denmark":
            return item["league"]["id"]
    return None

def pick_sample_fixture(league_id: int, seasons=(2023, 2022, 2021)) -> dict | None:
    """Find en afsluttet kamp vi kan bruge til at slå events/lineups osv. op."""
    for yr in seasons:
        js = throttled_get("/fixtures", {"league": league_id, "season": yr})
        for fx in js.get("response", []):
            stat = (fx.get("fixture", {}).get("status") or {}).get("short")
            if stat == "FT":
                return {
                    "season": yr,
                    "fixture_id": fx["fixture"]["id"],
                    "home_id": fx["teams"]["home"]["id"],
                    "away_id": fx["teams"]["away"]["id"],
                }
    return None

def pick_player_from_lineup(fixture_id: int) -> int | None:
    """Tag første spiller-id fra lineup for den valgte kamp."""
    js = throttled_get("/fixtures/lineups", {"fixture": fixture_id})
    for item in js.get("response", []):
        # prøv startopstilling
        for p in (item.get("startXI") or []):
            pid = ((p.get("player") or {}).get("id"))
            if pid:
                return pid
        # fallback: bænken
        for p in (item.get("substitutes") or []):
            pid = ((p.get("player") or {}).get("id"))
            if pid:
                return pid
    return None

# ---------- hovedkørsel ----------
def main():
    parser = argparse.ArgumentParser(description="Diagnose af API-Football features")
    parser.add_argument("--mode", choices=["quick", "full"], default="quick",
                        help="quick = få kald; full = alle kald (langsommere)")
    args = parser.parse_args()

    report = {"base_url": BASE_URL, "mode": args.mode, "probed": []}

    lid = find_superliga_id()
    if not lid:
        print("❌ Kunne ikke finde Superliga via search=Superliga")
        sys.exit(2)
    print(f"✅ Superliga ID: {lid}")

    sample = pick_sample_fixture(lid)
    if not sample:
        print("⚠️ Fandt ingen afsluttet kamp i 2021–2023")
        sys.exit(3)

    print(f"🔎 Bruger fixture {sample['fixture_id']} (season {sample['season']})")

    player_id = pick_player_from_lineup(sample["fixture_id"])  # til trophies/sidelined
    if player_id:
        print(f"👤 Eksempelspiller fra lineup: {player_id}")
    else:
        print("⚠️ Kunne ikke finde spiller fra lineup — trophies/sidelined springes muligvis over")

    # --- endpoints at teste ---
    quick_checks = [
        ("countries", "/countries", {}),
        ("seasons",   "/leagues/seasons", {}),
        ("leagues(DK)","/leagues", {"country":"Denmark","season":sample["season"]}),
        ("standings", "/standings", {"league": lid, "season": sample["season"]}),
        ("teams",     "/teams", {"league": lid, "season": sample["season"]}),
        ("fixtures",  "/fixtures", {"league": lid, "season": sample["season"]}),
        ("events",    "/fixtures/events", {"fixture": sample["fixture_id"]}),
        ("lineups",   "/fixtures/lineups", {"fixture": sample["fixture_id"]}),
        ("stats_teams","/fixtures/statistics", {"fixture": sample["fixture_id"]}),
    ]

    full_extra = [
        ("stats_players","/fixtures/players", {"fixture": sample["fixture_id"]}),
        ("h2h",       "/fixtures/headtohead", {"h2h": f"{sample['home_id']}-{sample['away_id']}"}),
        ("injuries",  "/injuries", {"league": lid, "season": sample["season"]}),
        ("odds_prematch","/odds", {"fixture": sample["fixture_id"]}),
        ("odds_inplay",  "/odds/live", {}),
        ("predictions","/predictions", {"fixture": sample["fixture_id"]}),
        ("topscorers","/players/topscorers", {"league": lid, "season": sample["season"]}),
        # kræver player_id:
        ("trophies",  "/trophies", {"player": player_id} if player_id else None),
        ("sidelined", "/sidelined", {"player": player_id} if player_id else None),
    ]

    checks = quick_checks if args.mode == "quick" else quick_checks + full_extra

    for name, path, params in checks:
        if params is None:
            st, meta = "SKIPPED", "mangler player_id"
        else:
            js = throttled_get(path, params)
            st, meta = status_of(js)
        print(f"{name:<16} -> {st} {meta}")
        report["probed"].append({"endpoint": name, "path": path, "params": params, "status": st, "meta": meta})

    out_path = REPORTS_DIR / "apifootball_feature_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📝 Rapport gemt: {out_path}")

if __name__ == "__main__":
    main()
