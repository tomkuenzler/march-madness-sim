"""
odds.py

Fetches NCAA Tournament betting odds from The Odds API and computes
edges against our Monte Carlo model.

Edge calculation:
  1. Fetch American odds for each team to win the tournament
  2. Convert to raw implied probability
  3. Remove the vig by normalizing across all outcomes
  4. Compute edge = model_pct - no_vig_implied_pct
  5. Flag edges above 5% threshold as value bets
"""

import os
import requests
from typing import Optional

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
SPORT = "basketball_ncaab_championship_winner"
REGIONS = "us"
BOOKMAKER = "fanduel"
EDGE_THRESHOLD = 0.05


def american_to_implied(odds: int) -> float:
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def remove_vig(raw_probs: list[float]) -> list[float]:
    total = sum(raw_probs)
    if total <= 0:
        return raw_probs
    return [p / total for p in raw_probs]


def compute_edge(model_pct: float, no_vig_pct: float) -> float:
    return round(model_pct - no_vig_pct, 4)


def edge_rating(edge: float) -> str:
    if edge >= 0.10: return "Strong Value"
    if edge >= 0.05: return "Value"
    if edge >= 0.00: return "Slight Value"
    if edge >= -0.05: return "Fair"
    return "Avoid"


def fetch_tournament_odds() -> Optional[list]:
    if not ODDS_API_KEY:
        print("[ODDS] No API key set")
        return None

    print(f"[ODDS] API key found: {ODDS_API_KEY[:8]}...")

    try:
        url = f"{ODDS_API_BASE}/sports/{SPORT}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": REGIONS,
            "markets": "outrights",
            "bookmakers": BOOKMAKER,
            "oddsFormat": "american",
        }
        print(f"[ODDS] Fetching: {url}")
        resp = requests.get(url, params=params, timeout=15)
        print(f"[ODDS] Status: {resp.status_code}")
        print(f"[ODDS] Response preview: {resp.text[:300]}")

        remaining = resp.headers.get("x-requests-remaining", "?")
        used = resp.headers.get("x-requests-used", "?")
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

    teams_sim = simulation_results.get("teams", {})

    # Take the first (and usually only) futures event
    futures_event = raw[0]

    bookmakers = futures_event.get("bookmakers", [])
    if not bookmakers:
        print("[ODDS] No bookmakers available yet — lines not posted")
        return {
            "error": "No bookmaker lines available yet — check back once lines are posted",
            "available": False,
            "commence_time": futures_event.get("commence_time"),
        }

    # Try FanDuel first, fall back to any available bookmaker
    bookmaker_data = next(
        (bm for bm in bookmakers if bm.get("key") == BOOKMAKER),
        None
    ) or bookmakers[0]

    print(f"[ODDS] Using bookmaker: {bookmaker_data.get('key')}")

    # Find the outrights market
    market_data = next(
        (m for m in bookmaker_data.get("markets", [])
         if m.get("key") in ("outrights", "h2h", "winner")),
        None
    )

    if not market_data:
        print("[ODDS] No outrights market found in bookmaker data")
        return {}

    outcomes = market_data.get("outcomes", [])
    if not outcomes:
        print("[ODDS] No outcomes in market")
        return {}

    print(f"[ODDS] Found {len(outcomes)} team outcomes")

    # Build odds map and remove vig
    team_odds = {
        o["name"].strip(): int(o["price"])
        for o in outcomes
        if o.get("name") and o.get("price") is not None
    }

    names = list(team_odds.keys())
    raw_probs = [american_to_implied(team_odds[n]) for n in names]
    no_vig_probs = remove_vig(raw_probs)
    no_vig_map = dict(zip(names, no_vig_probs))

    # Match simulation teams to odds and compute edges
    result_teams = {}
    for team_name, team_data in teams_sim.items():
        # Exact match first, then partial
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

        american = team_odds[odds_name]
        raw_implied = american_to_implied(american)
        no_vig = no_vig_map.get(odds_name, raw_implied)
        model_pct = team_data.get("advancement", {}).get("Champion", 0)
        edge = compute_edge(model_pct, no_vig)
        odds_str = f"+{american}" if american > 0 else str(american)

        result_teams[team_name] = {
            "seed":           team_data.get("seed"),
            "region":         team_data.get("region"),
            "odds":           odds_str,
            "american":       american,
            "raw_implied":    round(raw_implied, 4),
            "no_vig_implied": round(no_vig, 4),
            "model_pct":      round(model_pct, 4),
            "edge":           edge,
            "edge_pct":       f"{edge * 100:+.1f}%",
            "rating":         edge_rating(edge),
            "is_value":       edge >= EDGE_THRESHOLD,
        }

    return {
        "bookmaker":    bookmaker_data.get("key"),
        "market":       "Tournament Winner",
        "round":        "Champion",
        "last_updated": bookmaker_data.get("last_update", ""),
        "teams":        result_teams,
        "note":         "Probabilities are no-vig (juice removed). Edge = Model% - No-Vig Implied%.",
    }


def build_odds_summary(simulation_results: dict) -> dict:
    if not ODDS_API_KEY:
        return {"error": "ODDS_API_KEY not configured", "available": False}

    raw = fetch_tournament_odds()
    if raw is None:
        return {"error": "Failed to fetch odds from The Odds API", "available": False}

    parsed = parse_odds_response(raw, simulation_results)
    if not parsed:
        return {
            "error": "Could not parse odds — market may not be available yet",
            "available": False,
        }

    # If parse returned an error dict (no bookmakers yet), pass it through
    if "error" in parsed:
        return parsed

    return {**parsed, "available": True}


# ---------------------------------------------------------------------------
# Round-by-round FanDuel odds from CSV
# ---------------------------------------------------------------------------

FANDUEL_CSV = os.path.join(os.path.dirname(__file__), "data", "fanduel_odds.csv")

ROUND_ADV_KEYS_ORDERED = ['R32', 'S16', 'E8', 'FF', 'Championship']

ROUND_DISPLAY = {
    'R32': 'Round of 32',
    'S16': 'Sweet 16',
    'E8':  'Elite 8',
    'FF':  'Final Four',
    'Championship': 'Championship',
}

def load_fanduel_odds(simulation_results: dict) -> dict:
    """
    Load FanDuel round-by-round advancement odds from CSV and compute
    edges against our model for every team and round.

    Returns:
    {
        "available": True,
        "bookmaker": "FanDuel",
        "teams": {
            "Duke": {
                "seed": 1, "region": "East",
                "rounds": {
                    "R32": {
                        "odds": "-50000", "american": -50000,
                        "raw_implied": 0.998, "no_vig_implied": 0.992,
                        "model_pct": 0.992, "edge": 0.000, "edge_pct": "+0.0%",
                        "rating": "Slight Value", "is_value": False
                    },
                    ...
                }
            }
        }
    }
    """
    import pandas as pd

    if not os.path.exists(FANDUEL_CSV):
        return {"available": False, "message": "fanduel_odds.csv not found in backend/data/"}

    try:
        df = pd.read_csv(FANDUEL_CSV)
        df.columns = df.columns.str.strip()
        df['Team'] = df['Team'].str.strip()
    except Exception as e:
        return {"available": False, "message": f"Error reading fanduel_odds.csv: {e}"}

    teams_sim = simulation_results.get("teams", {})

    # Build odds map per round
    # NOTE: For advancement odds we do NOT normalize across all teams since
    # each bet is a standalone market (not a pool like tournament winner).
    # We use raw implied probability directly.
    # For Champion (futures pool) we DO remove vig across all teams.
    round_odds_map = {}
    for r in ROUND_ADV_KEYS_ORDERED:
        if r not in df.columns:
            continue
        odds_for_round = {}
        for _, row in df.iterrows():
            val = str(row.get(r, '')).strip()
            if val and val not in ('', 'nan'):
                try:
                    odds_for_round[row['Team']] = int(float(val))
                except ValueError:
                    pass
        round_odds_map[r] = odds_for_round

    # For Champion round only: remove vig (pool market)
    round_no_vig = {}
    for r, odds_dict in round_odds_map.items():
        names = list(odds_dict.keys())
        raw_probs = [american_to_implied(odds_dict[n]) for n in names]
        if r == 'Champion':
            no_vig_list = remove_vig(raw_probs)
        else:
            no_vig_list = raw_probs  # use raw implied for advancement bets
        round_no_vig[r] = dict(zip(names, no_vig_list))

    # Build result per simulation team
    result_teams = {}
    for team_name, team_data in teams_sim.items():
        adv = team_data.get("advancement", {})

        # Match team name (exact first, then partial)
        def find_csv_name(name):
            # Exact match first
            if name in round_odds_map.get('R32', {}):
                return name
            # Check any round for exact match
            for r_odds in round_odds_map.values():
                if name in r_odds:
                    return name
            # Fuzzy: sort by length descending so "Michigan St." matches before "Michigan"
            all_csv_names = list((round_odds_map.get('E8') or round_odds_map.get('R32') or {}).keys())
            all_csv_names.sort(key=len, reverse=True)
            for csv_name in all_csv_names:
                if name.lower() == csv_name.lower():
                    return csv_name
                # Only match if BOTH are substrings of each other AND lengths are close
                if (name.lower() in csv_name.lower() or csv_name.lower() in name.lower()):
                    # Avoid matching "Iowa" to "Iowa St." — require length similarity
                    if abs(len(name) - len(csv_name)) <= 3:
                        return csv_name
            return None

        csv_name = find_csv_name(team_name)

        rounds_data = {}
        for r in ROUND_ADV_KEYS_ORDERED:
            odds_dict = round_odds_map.get(r, {})
            no_vig_dict = round_no_vig.get(r, {})

            lookup = csv_name if csv_name and csv_name in odds_dict else None
            if not lookup:
                # Try partial match within this round
                lookup = next(
                    (n for n in odds_dict
                     if team_name.lower() in n.lower() or n.lower() in team_name.lower()),
                    None
                )

            if not lookup:
                rounds_data[r] = None
                continue

            american = odds_dict[lookup]
            raw_implied = american_to_implied(american)
            no_vig = no_vig_dict.get(lookup, raw_implied)

            # Model advancement % for this round
            model_pct = adv.get(r, 0)
            edge = compute_edge(model_pct, no_vig)
            odds_str = f"+{american}" if american > 0 else str(american)

            # Convert model probability to American odds for display
            def pct_to_american(p):
                if p <= 0: return "+99999"
                if p >= 1: return "-99999"
                if p >= 0.5:
                    return str(int(round(-p / (1 - p) * 100)))
                else:
                    return f"+{int(round((1 - p) / p * 100))}"

            rounds_data[r] = {
                "odds":           odds_str,
                "american":       american,
                "raw_implied":    round(raw_implied, 4),
                "no_vig_implied": round(no_vig, 4),
                "model_pct":      round(model_pct, 4),
                "model_odds":     pct_to_american(model_pct),
                "edge":           edge,
                "edge_pct":       f"{edge * 100:+.1f}%",
                "rating":         edge_rating(edge),
                "is_value":       edge >= EDGE_THRESHOLD,
            }

        result_teams[team_name] = {
            "seed":   team_data.get("seed"),
            "region": team_data.get("region"),
            "rounds": rounds_data,
        }

    return {
        "available": True,
        "bookmaker": "FanDuel",
        "note": "No-vig implied probabilities. Edge = Model% − No-Vig Implied%.",
        "teams": result_teams,
    }
