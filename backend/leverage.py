"""
leverage.py

Computes leverage scores by comparing our Monte Carlo model's advancement
probabilities against consensus bracket pick percentages from:
  - Yahoo Tourney Pick'em
  - ESPN Tournament Challenge
  - NCAA.com

Leverage = Model% - Consensus%
Positive = underowned relative to true odds (potential value)
Negative = overowned relative to true odds (potential fade)

CSV format expected (one file per source):
  Team,R32,S16,E8,FF,Championship,Champion
  Duke,91%,67%,41%,28%,18%,30%
  ...

Percentages can be "91%", "91.0%", or "0.91" — all handled.
"""

import os
import pandas as pd
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

CONSENSUS_FILES = {
    "yahoo": os.path.join(DATA_DIR, "yahoo_picks.csv"),
    "espn":  os.path.join(DATA_DIR, "espn_picks.csv"),
    "ncaa":  os.path.join(DATA_DIR, "ncaa_picks.csv"),
}

ROUNDS = ["R32", "S16", "E8", "FF", "Championship", "Champion"]

ROUND_LABELS = {
    "R32":          "Round of 32",
    "S16":          "Sweet 16",
    "E8":           "Elite 8",
    "FF":           "Final Four",
    "Championship": "Championship",
    "Champion":     "Champion",
}


def _parse_pct(val) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    has_pct_sign = '%' in s
    s = s.replace('%', '')
    try:
        f = float(s)
        if has_pct_sign:
            return f / 100.0
        return f if f <= 1.0 else f / 100.0
    except ValueError:
        return None


def load_consensus_picks() -> Optional[dict[str, dict[str, float]]]:
    """
    Load and average consensus pick percentages across all available sources.
    Returns dict: { team_name: { round_key: avg_pct } }
    Returns None if no source files exist yet.
    """
    source_data = {}

    for source, filepath in CONSENSUS_FILES.items():
        if not os.path.exists(filepath):
            print(f"[LEVERAGE] No file found for {source} at {filepath} — skipping")
            continue

        try:
            df = pd.read_csv(filepath)
            df.columns = df.columns.str.strip()

            # Normalize team name column
            name_col = next(
                (c for c in df.columns if c.lower() in ("team", "name")), None
            )
            if not name_col:
                print(f"[LEVERAGE] {source}: no 'Team' column found")
                continue

            df = df.rename(columns={name_col: "Team"})
            df["Team"] = df["Team"].str.strip()

            picks = {}
            for _, row in df.iterrows():
                team = row["Team"]
                rounds = {}
                for r in ROUNDS:
                    if r in df.columns:
                        pct = _parse_pct(row.get(r))
                        if pct is not None:
                            rounds[r] = pct
                if rounds:
                    picks[team] = rounds

            source_data[source] = picks
            print(f"[LEVERAGE] Loaded {len(picks)} teams from {source}")

        except Exception as e:
            print(f"[LEVERAGE] Error loading {source}: {e}")

    if not source_data:
        return None

    # Average across all available sources
    all_teams = set()
    for picks in source_data.values():
        all_teams.update(picks.keys())

    consensus = {}
    for team in all_teams:
        team_rounds = {}
        for r in ROUNDS:
            values = [
                picks[team][r]
                for picks in source_data.values()
                if team in picks and r in picks[team]
            ]
            if values:
                team_rounds[r] = sum(values) / len(values)
        if team_rounds:
            consensus[team] = team_rounds

    print(f"[LEVERAGE] Consensus built for {len(consensus)} teams from {len(source_data)} source(s)")
    return consensus


def compute_leverage(
    simulation_results: dict,
    consensus: dict[str, dict[str, float]],
) -> dict:
    """
    Compute leverage scores for every team and round.

    Returns:
    {
        "sources_loaded": ["yahoo", "espn"],
        "teams": {
            "Duke": {
                "seed": 1, "region": "East",
                "leverage": {
                    "R32":          { "model": 0.99, "consensus": 0.91, "leverage": 0.08 },
                    "S16":          { "model": 0.86, "consensus": 0.67, "leverage": 0.19 },
                    ...
                }
            }
        }
    }
    """
    if not simulation_results or not consensus:
        return {}

    teams_sim = simulation_results.get("teams", {})
    result = {}

    for team_name, team_data in teams_sim.items():
        adv = team_data.get("advancement", {})
        team_consensus = consensus.get(team_name, {})

        leverage_rounds = {}
        for r in ROUNDS:
            model_pct = adv.get(r)
            cons_pct  = team_consensus.get(r)

            if model_pct is None:
                continue

            leverage_rounds[r] = {
                "model":     round(model_pct, 4),
                "consensus": round(cons_pct, 4) if cons_pct is not None else None,
                "leverage":  round(model_pct - cons_pct, 4) if cons_pct is not None else None,
                "label":     ROUND_LABELS[r],
            }

        result[team_name] = {
            "seed":     team_data.get("seed"),
            "region":   team_data.get("region"),
            "leverage": leverage_rounds,
        }

    sources_available = [
        s for s, fp in CONSENSUS_FILES.items() if os.path.exists(fp)
    ]

    return {
        "sources_loaded": sources_available,
        "teams": result,
    }
