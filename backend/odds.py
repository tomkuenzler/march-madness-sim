"""
odds.py

Fetches NCAA Tournament betting odds from The Odds API and computes
edges against our Monte Carlo model.

Edge calculation philosophy:
  Simple direct comparison — no vig removal.
  Edge = Model Implied% - FanDuel Implied%

  If FanDuel has a team at -300 (75.0% implied) and our model says
  72.5%, the edge is -2.5% — a bad bet, regardless of vig.
  The vig is already baked into FanDuel's number.
"""

import os
import json
import requests
from typing import Optional

ODDS_API_KEY  = os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
SPORT         = "basketball_ncaab_championship_winner"
REGIONS_US    = "us"
BOOKMAKER     = "fanduel"
EDGE_THRESHOLD = 0.03

FANDUEL_CSV  = os.path.join(os.path.dirname(__file__), "data", "fanduel_odds.csv")
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "data", "results.json")

ROUND_ADV_KEYS_ORDERED = ['R32', 'S16', 'E8', 'FF', 'Championship', 'Champion']


def american_to_implied(odds: int) -> float:
    """Convert American odds to implied probability (raw, no vig removal)."""
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def compute_edge(model_pct: float, fd_implied: float) -> float:
    """Edge = model implied probability minus FanDuel implied probability."""
    return round(model_pct - fd_implied, 4)


def edge_rating(edge: float) -> str:
    if edge >= 0.10: return "Strong Value"
    if edge >= 0.05: return "Value"
    if edge >= 0.00: return "Slight Value"
    if edge >= -0.05: return "Fair"
    return "Avoid"


def pct_to_american(p: float) -> str:
    """Convert probability to American odds string."""
    if p <= 0: return "+99999"
    if p >= 1: return "-99999"
    if p >= 0.5:
        return str(int(round(-p / (1 - p) * 100)))
    return f"+{int(round((1 - p) / p * 100))}"


# ---------------------------------------------------------------------------
# The Odds API — tournament winner futures (BetMGM fallback)
# ---------------------------------------------------------------------------

def fetch_tournament_odds() -> Optional[list]:
    if not ODDS_API_KEY:
        print("[ODDS] No API key set")
        return None
    print(f"[ODDS] API key found: {ODDS_API_KEY[:8]}...")
    try:
        url = f"{ODDS_API_BASE}/sports/{SPORT}/odds"
        params = {
            "apiKey":     ODDS_API_KEY,
            "regions":    REGIONS_US,
            "markets":    "outrights",
            "oddsFormat": "american",
        }
        print(f"[ODDS] Fetching: {url}")
        resp = requests.get(url, params=params, timeout=15)
        print(f"[ODDS] Status: {resp.status_code}")
        print(f"[ODDS] Response preview: {resp.text[:300]}")
        remaining = resp.headers.get("x-requests-remaining", "?")
        used      = resp.headers.get("x-requests-used", "?")
        print(f"[ODDS] Requests used: {used}, remaining: {remaining}")
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        print("[ODDS] Request timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[ODDS] Request failed: {e}")
        return None


def parse_odds_response(raw: list, simulation_results: dict) -> dict:
    if not raw or not simulation_results:
        return {}

    teams_sim     = simulation_results.get("teams", {})
    futures_event = raw[0]
    bookmakers    = futures_event.get("bookmakers", [])

    if not bookmakers:
        print("[ODDS] No bookmakers available yet")
        return {
            "error":          "No bookmaker lines available yet",
            "available":      False,
            "commence_time":  futures_event.get("commence_time"),
        }

    bookmaker_data = next(
        (bm for bm in bookmakers if bm.get("key") == BOOKMAKER), None
    ) or bookmakers[0]
    print(f"[ODDS] Using bookmaker: {bookmaker_data.get('key')}")

    market_data = next(
        (m for m in bookmaker_data.get("markets", [])
         if m.get("key") in ("outrights", "h2h", "winner")),
        None
    )
    if not market_data:
        print("[ODDS] No outrights market found")
        return {}

    outcomes = market_data.get("outcomes", [])
    if not outcomes:
        return {}
    print(f"[ODDS] Found {len(outcomes)} team outcomes")

    team_odds = {
        o["name"].strip(): int(o["price"])
        for o in outcomes
        if o.get("name") and o.get("price") is not None
    }

    result_teams = {}
    for team_name, team_data in teams_sim.items():
        if team_name in team_odds:
            odds_name = team_name
        else:
            odds_name = next(
                (n for n in team_odds
                 if team_name.lower() in n.lower() or n.lower() in team_name.lower()),
                None
            )
        if not odds_name:
            continue

        american    = team_odds[odds_name]
        fd_implied  = american_to_implied(american)
        model_pct   = team_data.get("advancement", {}).get("Champion", 0)
        edge        = compute_edge(model_pct, fd_implied)
        odds_str    = f"+{american}" if american > 0 else str(american)

        result_teams[team_name] = {
            "seed":       team_data.get("seed"),
            "region":     team_data.get("region"),
            "odds":       odds_str,
            "american":   american,
            "fd_implied": round(fd_implied, 4),
            "model_pct":  round(model_pct, 4),
            "edge":       edge,
            "edge_pct":   f"{edge * 100:+.1f}%" if abs(edge) >= 0.0005 else "0.0%",
            "rating":     edge_rating(edge),
            "is_value":   edge >= EDGE_THRESHOLD,
        }

    return {
        "bookmaker":    bookmaker_data.get("key"),
        "market":       "Tournament Winner",
        "round":        "Champion",
        "last_updated": bookmaker_data.get("last_update", ""),
        "teams":        result_teams,
        "note":         "Edge = Model Implied% − FanDuel Implied%. Positive = model likes team more than book.",
    }


def build_odds_summary(simulation_results: dict) -> dict:
    if not ODDS_API_KEY:
        return {"error": "ODDS_API_KEY not configured", "available": False}
    raw = fetch_tournament_odds()
    if raw is None:
        return {"error": "Failed to fetch odds from The Odds API", "available": False}
    parsed = parse_odds_response(raw, simulation_results)
    if not parsed:
        return {"error": "Could not parse odds — market may not be available yet", "available": False}
    if "error" in parsed:
        return parsed
    return {**parsed, "available": True}


# ---------------------------------------------------------------------------
# FanDuel CSV — round-by-round advancement odds
# ---------------------------------------------------------------------------

def load_fanduel_odds(simulation_results: dict) -> dict:
    """
    Load FanDuel round-by-round advancement odds from CSV and compute
    edges against our model.

    Edge = Model Implied% - FanDuel Implied%
    Simple direct comparison. No vig removal.
    """
    import pandas as pd

    if not os.path.exists(FANDUEL_CSV):
        return {"available": False, "message": "fanduel_odds.csv not found in backend/data/"}

    try:
        df = pd.read_csv(FANDUEL_CSV)
        df.columns = df.columns.str.strip()
        df["Team"] = df["Team"].str.strip()
    except Exception as e:
        return {"available": False, "message": f"Error reading fanduel_odds.csv: {e}"}

    # Build odds map per round
    round_odds_map = {}
    for r in ROUND_ADV_KEYS_ORDERED:
        if r not in df.columns:
            continue
        odds_for_round = {}
        for _, row in df.iterrows():
            val = str(row.get(r, "")).strip()
            if val and val not in ("", "nan"):
                try:
                    odds_for_round[row["Team"]] = int(float(val))
                except ValueError:
                    pass
        round_odds_map[r] = odds_for_round

    teams_sim = simulation_results.get("teams", {})

    def find_csv_name(name, odds_dict):
        """Match simulation team name to CSV team name."""
        if name in odds_dict:
            return name
        # Sort longer names first to avoid partial matches (Michigan before Michigan St.)
        all_csv = sorted(odds_dict.keys(), key=len, reverse=True)
        for csv_name in all_csv:
            if name.lower() == csv_name.lower():
                return csv_name
            if (name.lower() in csv_name.lower() or csv_name.lower() in name.lower()):
                if abs(len(name) - len(csv_name)) <= 3:
                    return csv_name
        return None

    result_teams = {}
    for team_name, team_data in teams_sim.items():
        adv = team_data.get("advancement", {})

        rounds_data = {}
        for r in ROUND_ADV_KEYS_ORDERED:
            odds_dict = round_odds_map.get(r, {})
            csv_name  = find_csv_name(team_name, odds_dict)

            if not csv_name:
                rounds_data[r] = None
                continue

            american   = odds_dict[csv_name]
            fd_implied = american_to_implied(american)
            model_pct  = adv.get(r, 0)
            edge       = compute_edge(model_pct, fd_implied)
            odds_str   = f"+{american}" if american > 0 else str(american)

            rounds_data[r] = {
                "odds":        odds_str,
                "american":    american,
                "fd_implied":  round(fd_implied, 4),
                "model_pct":   round(model_pct, 4),
                "model_odds":  pct_to_american(model_pct),
                "edge":        edge,
                "edge_pct":    f"{edge * 100:+.1f}%" if abs(edge) >= 0.0005 else "0.0%",
                "rating":      edge_rating(edge),
                "is_value":    edge >= EDGE_THRESHOLD,
            }

        result_teams[team_name] = {
            "seed":   team_data.get("seed"),
            "region": team_data.get("region"),
            "rounds": rounds_data,
        }

    return {
        "available": True,
        "bookmaker": "FanDuel",
        "note":      "Edge = Model Implied% − FanDuel Implied%. Positive = model likes team more than book.",
        "teams":     result_teams,
    }
