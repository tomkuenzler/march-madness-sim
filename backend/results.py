"""
results.py

Persistent storage for actual tournament game results and scores.
"""

import os
import json

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "data", "results.json")
SCORES_FILE  = os.path.join(os.path.dirname(__file__), "data", "scores.json")


def load_results() -> dict:
    if not os.path.exists(RESULTS_FILE):
        return {}
    try:
        with open(RESULTS_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[RESULTS] Error loading results: {e}")
        return {}


def save_results(results: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
        with open(RESULTS_FILE, "w") as f:
            json.dump(results, f, indent=2)
        return True
    except Exception as e:
        print(f"[RESULTS] Error saving results: {e}")
        return False


def load_scores() -> dict:
    if not os.path.exists(SCORES_FILE):
        return {}
    try:
        with open(SCORES_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[RESULTS] Error loading scores: {e}")
        return {}


def save_scores(scores: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(SCORES_FILE), exist_ok=True)
        with open(SCORES_FILE, "w") as f:
            json.dump(scores, f, indent=2)
        return True
    except Exception as e:
        print(f"[RESULTS] Error saving scores: {e}")
        return False


def set_result(game_id: str, winner: str) -> dict:
    results = load_results()
    results[game_id] = winner
    save_results(results)
    print(f"[RESULTS] Set {game_id} -> {winner} ({len(results)} total results)")
    return results


def clear_result(game_id: str) -> dict:
    results = load_results()
    results.pop(game_id, None)
    save_results(results)
    return results


def clear_all_results() -> dict:
    save_results({})
    print("[RESULTS] All results cleared")
    return {}


def merge_with_locks(results: dict, locked: dict) -> dict:
    merged = {**locked}
    merged.update(results)
    return merged
