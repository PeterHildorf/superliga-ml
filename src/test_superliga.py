import os
from dotenv import load_dotenv
import httpx
import sys
from pprint import pprint

load_dotenv()
API_KEY = os.getenv("APIFOOTBALL_KEY")
if not API_KEY:
    print("⚠️  APIFOOTBALL_KEY mangler i .env")
    sys.exit(1)

# Vælg base: direkte API-Football (typisk) eller RapidAPI fallback
BASE_URL = os.getenv("APIFOOTBALL_BASE", "https://v3.football.api-sports.io")
USE_RAPIDAPI = "rapidapi" in BASE_URL

if USE_RAPIDAPI:
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "v3.football.api-sports.io",
        "Accept": "application/json",
    }
else:
    headers = {
        "x-apisports-key": API_KEY,
        "Accept": "application/json",
    }

def get(path, params=None):
    url = f"{BASE_URL}{path}"
    r = httpx.get(url, params=params, headers=headers, timeout=30)
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        print("❌ HTTP-fejl:", e)
        print("Body:", r.text[:1000])
        raise
    data = r.json()
    if data.get("errors"):
        print("⚠️ API errors:", data["errors"])
    return data

def find_superliga_id(season=2024):
    # 1) Prøv country=Denmark
    resp = get("/leagues", params={"country": "Denmark", "season": season})
    cand = []
    for item in resp.get("response", []):
        name = (item.get("league") or {}).get("name", "")
        if "superliga" in name.lower():
            return (item["league"]["id"], item["league"]["name"], "country=Denmark")
        cand.append((item.get("league", {}).get("id"), name))

    # 2) Prøv search=Superliga
    resp2 = get("/leagues", params={"search": "Superliga"})
    for item in resp2.get("response", []):
        name = (item.get("league") or {}).get("name", "")
        country = (item.get("country") or {}).get("name", "")
        seasons = [s.get("year") for s in item.get("seasons", []) if "year" in s]
        if country and country.lower() == "denmark":
            # vælg den med den rigtige sæson, hvis muligt
            if season in seasons or not seasons:
                return (item["league"]["id"], name, "search=Superliga")

    # 3) Prøv country code (DK)
    resp3 = get("/leagues", params={"code": "dk", "season": season})
    for item in resp3.get("response", []):
        name = (item.get("league") or {}).get("name", "")
        if "superliga" in name.lower():
            return (item["league"]["id"], name, "code=dk")

    # Hvis stadig intet, print kandidater fra første kald
    print("🤔 Fandt ikke 'Superliga'. Kandidater (country=Denmark):")
    for i, n in cand[:10]:
        print(" -", i, n)
    return None, None, None

def main():
    print("➡️  Tester adgang og rate-limit headers...")
    ping = get("/status")
    print("Status ok. Server tid:", ping.get("response", {}).get("time", "?"))

    season = 2024  # 2024 dækker typisk sæson 2024/25
    league_id, league_name, method = find_superliga_id(season)
    if not league_id:
        print("⚠️  Kunne ikke finde Superliga via nogen metode.")
        print("Tip: Print hele /leagues for Denmark uden season-filter for at se hvad der findes.")
        # Ekstra debug:
        dbg = get("/leagues", params={"country": "Denmark"})
        print("Uddrag af leagues for Denmark:")
        for item in dbg.get("response", [])[:5]:
            pprint({
                "id": item.get("league", {}).get("id"),
                "name": item.get("league", {}).get("name"),
                "type": item.get("league", {}).get("type"),
                "seasons": [s.get("year") for s in item.get("seasons", [])][:5]
            })
        return

    print(f"✅ Fandt {league_name} (ID={league_id}) via {method}")

    # Hent fixtures for den sæson/ligaid
    fx = get("/fixtures", params={"league": league_id, "season": season})
    fixtures = fx.get("response", [])
    print(f"✅ Hentede {len(fixtures)} kampe fra {league_name} ({season})")

    for m in fixtures[:5]:
        date = m["fixture"]["date"]
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]
        print(f" - {date}: {home} vs {away}")

if __name__ == "__main__":
    main()
