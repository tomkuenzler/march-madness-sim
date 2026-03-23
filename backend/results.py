"""
results.py

Persistent storage for actual tournament game results.
Results are stored in backend/data/results.json and survive server restarts.

Results are separate from user's hypothetical locked_results — they represent
real completed games and are always treated as 100% certain in simulations.
"""

import os
import json
from typing import Optional

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "data", "results.json")


def load_results() -> dict[str, str]:
    """
    Load results from disk.
    Returns dict of { game_id: winning_team_name }
    """
    if not os.path.exists(RESULTS_FILE):
        return {}
    try:
        with open(RESULTS_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception as e:
        print(f"[RESULTS] Error loading results: {e}")
        return {}


def save_results(results: dict[str, str]) -> bool:
    """Save results to disk. Returns True on success."""
    try:
        os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
        with open(RESULTS_FILE, "w") as f:
            json.dump(results, f, indent=2)
        return True
    except Exception as e:
        print(f"[RESULTS] Error saving results: {e}")
        return False


def set_result(game_id: str, winner: str) -> dict[str, str]:
    """Set a single game result and persist to disk."""
    results = load_results()
    results[game_id] = winner
    save_results(results)
    print(f"[RESULTS] Set {game_id} -> {winner} ({len(results)} total results)")
    return results


def clear_result(game_id: str) -> dict[str, str]:
    """Remove a single game result."""
    results = load_results()
    results.pop(game_id, None)
    save_results(results)
    return results


def clear_all_results() -> dict[str, str]:
    """Clear all stored results."""
    save_results({})
    print("[RESULTS] All results cleared")
    return {}


def merge_with_locks(
    results: dict[str, str],
    locked: dict[str, str]
) -> dict[str, str]:
    """
    Merge actual results with user's hypothetical locks.
    Results take precedence over locks for the same game.
    """
    merged = {**locked}
    merged.update(results)  # results override locks
    return merged
