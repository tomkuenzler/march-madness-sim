"""
main.py
FastAPI backend for the March Madness Monte Carlo simulator.
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os

from bracket import load_teams_from_csv, Team
from simulator import run_monte_carlo
from leverage import load_consensus_picks, compute_leverage
from odds import build_odds_summary
from results import load_results, set_result, clear_result, clear_all_results, merge_with_locks

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="March Madness Simulator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        "https://march-madness-sim-nine.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "kenpom.csv")
N_SIMULATIONS = int(os.environ.get("N_SIMULATIONS", "10000"))

_teams: dict[str, Team] = {}
_simulation_cache: dict = {}
_locked_results: dict[str, str] = {}
_consensus_cache: Optional[dict] = None
_leverage_cache: dict = {}
_odds_cache: dict = {}
_actual_results: dict[str, str] = {}  # persistent real game results

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    global _teams, _simulation_cache, _consensus_cache, _leverage_cache

    if not os.path.exists(CSV_PATH):
        print(f"[WARNING] KenPom CSV not found at {CSV_PATH}")
        return

    try:
        _teams = load_teams_from_csv(CSV_PATH)
        print(f"[OK] Loaded {len(_teams)} teams from CSV")
        _simulation_cache = run_monte_carlo(_teams, N_SIMULATIONS, _locked_results)
        print(f"[OK] Initial simulation complete ({N_SIMULATIONS:,} runs)")
    except Exception as e:
        print(f"[ERROR] Failed to load/simulate: {e}")
        raise

    # Load leverage if consensus CSVs exist
    try:
        _consensus_cache = load_consensus_picks()
        if _consensus_cache and _simulation_cache:
            _leverage_cache = compute_leverage(_simulation_cache, _consensus_cache)
            print(f"[OK] Leverage computed for {len(_leverage_cache.get('teams', {}))} teams")
        else:
            print("[INFO] Leverage skipped — add consensus CSVs to backend/data/ when ready")
    except Exception as e:
        print(f"[WARNING] Leverage loading failed: {e}")

    # Load persisted game results
    global _actual_results
    _actual_results = load_results()
    if _actual_results:
        print(f"[OK] Loaded {len(_actual_results)} stored game results")
        # Re-run simulation with actual results merged in
        try:
            merged = merge_with_locks(_actual_results, _locked_results)
            _simulation_cache = run_monte_carlo(_teams, N_SIMULATIONS, merged)
            print(f"[OK] Simulation updated with actual results")
        except Exception as e:
            print(f"[WARNING] Could not re-run simulation with results: {e}")

# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    locked_results: Optional[dict[str, str]] = {}
    n_simulations: Optional[int] = N_SIMULATIONS

class LockGameRequest(BaseModel):
    game_id: str
    winner: Optional[str] = None

class MatchupRequest(BaseModel):
    team_a: str
    team_b: str

# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------

@app.get("/api/teams")
def get_teams():
    if not _teams:
        raise HTTPException(status_code=503, detail="Team data not loaded.")
    return {
        name: {
            "name": team.name,
            "seed": team.seed,
            "region": team.region,
            "adj_em": team.adj_em,
            "adj_o": team.adj_o,
            "adj_d": team.adj_d,
            "adj_t": team.adj_t,
        }
        for name, team in _teams.items()
    }

@app.get("/api/simulation")
def get_simulation():
    if not _simulation_cache:
        raise HTTPException(status_code=503, detail="Simulation not yet run.")
    return {**_simulation_cache, "locked_results": _locked_results, "actual_results": _actual_results}

@app.post("/api/simulate")
def run_simulation(req: SimulateRequest):
    global _simulation_cache, _locked_results, _leverage_cache
    if not _teams:
        raise HTTPException(status_code=503, detail="Team data not loaded.")
    locked = req.locked_results or {}
    n = max(1_000, min(req.n_simulations or N_SIMULATIONS, 100_000))
    try:
        _locked_results = locked
        merged = merge_with_locks(_actual_results, locked)  # ← add this
        _simulation_cache = run_monte_carlo(_teams, n, merged)  # ← use merged
        if _consensus_cache:
            _leverage_cache = compute_leverage(_simulation_cache, _consensus_cache)
        return {**_simulation_cache, "locked_results": _locked_results, "actual_results": _actual_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lock")
def lock_game(req: LockGameRequest):
    global _simulation_cache, _locked_results, _leverage_cache
    if not _teams:
        raise HTTPException(status_code=503, detail="Team data not loaded.")
    if req.winner is None:
        _locked_results.pop(req.game_id, None)
    else:
        _locked_results[req.game_id] = req.winner
    try:
        merged = merge_with_locks(_actual_results, _locked_results)  # ← add this
        _simulation_cache = run_monte_carlo(_teams, N_SIMULATIONS, merged)  # ← use merged
        if _consensus_cache:
            _leverage_cache = compute_leverage(_simulation_cache, _consensus_cache)
        return {**_simulation_cache, "locked_results": _locked_results, "actual_results": _actual_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/matchup")
def compute_matchup(req: MatchupRequest):
    if not _teams:
        raise HTTPException(status_code=503, detail="Team data not loaded.")
    team_a = _teams.get(req.team_a)
    team_b = _teams.get(req.team_b)
    if not team_a:
        raise HTTPException(status_code=404, detail=f"Team not found: {req.team_a}")
    if not team_b:
        raise HTTPException(status_code=404, detail=f"Team not found: {req.team_b}")
    from simulator import point_differential, win_probability
    diff = point_differential(team_a, team_b)
    prob_a = win_probability(team_a, team_b)
    return {
        "team_a": req.team_a,
        "team_b": req.team_b,
        "point_diff": round(diff, 2),
        "win_prob_a": round(prob_a, 4),
        "win_prob_b": round(1 - prob_a, 4),
        "favored": req.team_a if diff > 0 else req.team_b,
        "spread": round(abs(diff), 2),
        "upset_alert": abs(diff) < 3.0,
        "team_a_stats": {
            "seed": team_a.seed, "region": team_a.region,
            "adj_em": team_a.adj_em, "adj_o": team_a.adj_o,
            "adj_d": team_a.adj_d, "adj_t": team_a.adj_t,
        },
        "team_b_stats": {
            "seed": team_b.seed, "region": team_b.region,
            "adj_em": team_b.adj_em, "adj_o": team_b.adj_o,
            "adj_d": team_b.adj_d, "adj_t": team_b.adj_t,
        },
    }

# ---------------------------------------------------------------------------
# Results endpoints (persistent actual game results)
# ---------------------------------------------------------------------------

class SetResultRequest(BaseModel):
    game_id: str
    winner: str

@app.get("/api/results")
def get_results():
    """Return all stored actual game results."""
    return {"results": _actual_results, "count": len(_actual_results)}

@app.post("/api/results/set")
def set_game_result(req: SetResultRequest):
    """
    Mark a game as completed with a real winner.
    Persists to disk and re-runs simulation.
    """
    global _actual_results, _simulation_cache, _leverage_cache
    if not _teams:
        raise HTTPException(status_code=503, detail="Team data not loaded.")

    _actual_results = set_result(req.game_id, req.winner)

    try:
        merged = merge_with_locks(_actual_results, _locked_results)
        _simulation_cache = run_monte_carlo(_teams, N_SIMULATIONS, merged)
        if _consensus_cache:
            _leverage_cache = compute_leverage(_simulation_cache, _consensus_cache)
        return {
            **_simulation_cache,
            "locked_results": _locked_results,
            "actual_results": _actual_results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/results/clear")
def clear_game_results():
    """Clear all stored actual results and re-run simulation."""
    global _actual_results, _simulation_cache, _leverage_cache
    _actual_results = clear_all_results()
    try:
        _simulation_cache = run_monte_carlo(_teams, N_SIMULATIONS, _locked_results)
        if _consensus_cache:
            _leverage_cache = compute_leverage(_simulation_cache, _consensus_cache)
        return {
            **_simulation_cache,
            "locked_results": _locked_results,
            "actual_results": _actual_results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/results/single")
def clear_single_result(game_id: str):
    """Remove a single game result."""
    global _actual_results, _simulation_cache
    _actual_results = clear_result(game_id)
    try:
        merged = merge_with_locks(_actual_results, _locked_results)
        _simulation_cache = run_monte_carlo(_teams, N_SIMULATIONS, merged)
        return {"actual_results": _actual_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")

def health():
    return {
        "status": "ok",
        "teams_loaded": len(_teams),
        "simulation_ready": bool(_simulation_cache),
        "locked_games": len(_locked_results),
        "leverage_ready": bool(_leverage_cache),
        "odds_ready": bool(_odds_cache),
    }

# ---------------------------------------------------------------------------
# Leverage endpoints
# ---------------------------------------------------------------------------

@app.get("/api/leverage")
def get_leverage():
    if not _leverage_cache:
        return {
            "available": False,
            "message": "Leverage data not available. Add yahoo_picks.csv to backend/data/",
        }
    return {**_leverage_cache, "available": True}

@app.post("/api/leverage/refresh")
def refresh_leverage():
    global _consensus_cache, _leverage_cache
    _consensus_cache = load_consensus_picks()
    if _consensus_cache and _simulation_cache:
        _leverage_cache = compute_leverage(_simulation_cache, _consensus_cache)
        return {**_leverage_cache, "available": True}
    return {"available": False, "message": "Could not load consensus data"}

# ---------------------------------------------------------------------------
# Odds endpoints
# ---------------------------------------------------------------------------

@app.get("/api/odds")
def get_odds():
    if _odds_cache:
        return _odds_cache
    return {
        "available": False,
        "message": "Odds not yet fetched. Call POST /api/odds/refresh to load.",
    }

@app.get("/api/odds/rounds")
def get_round_odds():
    """Return FanDuel round-by-round advancement odds with edges."""
    if not _simulation_cache:
        raise HTTPException(status_code=503, detail="Simulation not yet run")
    from odds import load_fanduel_odds
    return load_fanduel_odds(_simulation_cache)

@app.post("/api/odds/refresh")
def refresh_odds():
    global _odds_cache
    if not _simulation_cache:
        raise HTTPException(status_code=503, detail="Simulation not yet run")
    _odds_cache = build_odds_summary(_simulation_cache)
    return _odds_cache

# ---------------------------------------------------------------------------
# ESPN auto-sync endpoint
# ---------------------------------------------------------------------------

@app.post("/api/results/sync")
def sync_results_from_espn():
    """
    Fetch completed NCAA Tournament results from ESPN and update results.json.
    Only adds new results — never overwrites existing ones.
    """
    global _actual_results, _simulation_cache, _leverage_cache
    if not _teams:
        raise HTTPException(status_code=503, detail="Team data not loaded.")

    from espn_sync import fetch_espn_results

    known_teams = set(_teams.keys())
    try:
        updated = fetch_espn_results(known_teams, _actual_results)
        new_count = len(updated) - len(_actual_results)

        if new_count > 0:
            from results import save_results
            save_results(updated)
            _actual_results = updated
            merged = merge_with_locks(_actual_results, _locked_results)
            _simulation_cache = run_monte_carlo(_teams, N_SIMULATIONS, merged)
            if _consensus_cache:
                _leverage_cache = compute_leverage(_simulation_cache, _consensus_cache)
            print(f"[ESPN] Synced {new_count} new results")
        else:
            print("[ESPN] No new results found")

        return {
            "new_results": new_count,
            "total_results": len(updated),
            "results": updated,
            "simulation_updated": new_count > 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ESPN sync failed: {e}")
