"""
main.py
FastAPI backend for the March Madness Monte Carlo simulator.

Endpoints:
  GET  /api/teams        - Raw team stats from KenPom CSV
  GET  /api/simulation   - Cached simulation results
  POST /api/simulate     - Re-run simulation (with optional locked results)
  POST /api/lock         - Update locked game winners and re-run
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os

from bracket import load_teams_from_csv, Team
from simulator import run_monte_carlo

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="March Madness Simulator", version="1.0.0")

# Allow the Svelte dev server (port 5173) to call the API
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
# State: loaded once at startup, cached after each simulation run
# ---------------------------------------------------------------------------

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "kenpom.csv")
N_SIMULATIONS = 10_000

_teams: dict[str, Team] = {}
_simulation_cache: dict = {}
_locked_results: dict[str, str] = {}   # game_id -> winning team name


# ---------------------------------------------------------------------------
# Startup: load CSV and run initial simulation
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    global _teams, _simulation_cache

    if not os.path.exists(CSV_PATH):
        print(f"[WARNING] KenPom CSV not found at {CSV_PATH}")
        print("Place your kenpom.csv in backend/data/ and restart the server.")
        return

    try:
        _teams = load_teams_from_csv(CSV_PATH)
        print(f"[OK] Loaded {len(_teams)} teams from CSV")
        _simulation_cache = run_monte_carlo(_teams, N_SIMULATIONS, _locked_results)
        print(f"[OK] Initial simulation complete ({N_SIMULATIONS:,} runs)")
    except Exception as e:
        print(f"[ERROR] Failed to load/simulate: {e}")
        raise


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    locked_results: Optional[dict[str, str]] = {}   # game_id -> team name
    n_simulations: Optional[int] = N_SIMULATIONS


class LockGameRequest(BaseModel):
    game_id: str
    winner: Optional[str] = None   # None = unlock the game

class MatchupRequest(BaseModel):
    team_a: str
    team_b: str

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/teams")
def get_teams():
    """Return raw team stats for all tournament teams."""
    if not _teams:
        raise HTTPException(status_code=503, detail="Team data not loaded. Check your kenpom.csv.")

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
    """Return the cached simulation results."""
    if not _simulation_cache:
        raise HTTPException(
            status_code=503,
            detail="Simulation not yet run. Check that kenpom.csv is loaded."
        )
    return {**_simulation_cache, "locked_results": _locked_results}


@app.post("/api/simulate")
def run_simulation(req: SimulateRequest):
    """
    Re-run the Monte Carlo simulation.
    Optionally pass locked_results to pin certain game winners.
    """
    global _simulation_cache, _locked_results

    if not _teams:
        raise HTTPException(status_code=503, detail="Team data not loaded.")

    locked = req.locked_results or {}
    n = max(1_000, min(req.n_simulations or N_SIMULATIONS, 100_000))

    try:
        _locked_results = locked
        _simulation_cache = run_monte_carlo(_teams, n, locked)
        return {**_simulation_cache, "locked_results": _locked_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lock")
def lock_game(req: LockGameRequest):
    """
    Lock or unlock a single game winner, then re-run the simulation.
    Send winner=null to unlock a previously locked game.
    """
    global _simulation_cache, _locked_results

    if not _teams:
        raise HTTPException(status_code=503, detail="Team data not loaded.")

    if req.winner is None:
        _locked_results.pop(req.game_id, None)
    else:
        _locked_results[req.game_id] = req.winner

    try:
        _simulation_cache = run_monte_carlo(_teams, N_SIMULATIONS, _locked_results)
        return {**_simulation_cache, "locked_results": _locked_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/matchup")
def compute_matchup(req: MatchupRequest):
    """
    Compute point spread and win probability for any two teams on demand.
    Used by the bracket modal for future round matchups.
    Does NOT run a simulation — pure math from KenPom stats.
    """
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
            "seed": team_a.seed,
            "region": team_a.region,
            "adj_em": team_a.adj_em,
            "adj_o": team_a.adj_o,
            "adj_d": team_a.adj_d,
            "adj_t": team_a.adj_t,
        },
        "team_b_stats": {
            "seed": team_b.seed,
            "region": team_b.region,
            "adj_em": team_b.adj_em,
            "adj_o": team_b.adj_o,
            "adj_d": team_b.adj_d,
            "adj_t": team_b.adj_t,
        },
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "teams_loaded": len(_teams),
        "simulation_ready": bool(_simulation_cache),
        "locked_games": len(_locked_results),
    }
