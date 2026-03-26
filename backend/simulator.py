"""
simulator.py
Monte Carlo simulation engine for the NCAA Tournament bracket.
Uses KenPom-derived NetRTG and Tempo to compute win probabilities,
then simulates N full tournaments to produce advancement odds.
"""

import random
from collections import defaultdict
from typing import Optional
from bracket import Team, Game, REGIONS, FIRST_ROUND_MATCHUPS, ROUND2_PAIRS, ROUND3_PAIRS, FINAL_FOUR_PAIRS
from scipy.stats import norm


# ---------------------------------------------------------------------------
# Win probability math
# ---------------------------------------------------------------------------

def point_differential(team_a: Team, team_b: Team) -> float:
    """
    Compute expected point differential for team_a vs team_b.
    Positive = team_a favored by that many points.
    Negative = team_b favored.

    Formula:
        diff = (NetRTG_A - NetRTG_B) * (Tempo_A + Tempo_B) / 200
    """
    return (team_a.adj_em - team_b.adj_em) * (team_a.adj_t + team_b.adj_t) / 200


def win_probability(team_a: Team, team_b: Team) -> float:
    """
    Convert point differential into win probability using a normal CDF.
    This is the standard KenPom methodology:
    - Compute expected margin
    - Assume actual margin is normally distributed around that with std_dev ~11
    - P(win) = P(margin > 0) = norm.cdf(diff / std_dev)
    
    std_dev of 11 is empirically validated for NCAA tournament games.
    Increase to 12-13 for more upsets, decrease to 10 for fewer.
    """
    diff = point_differential(team_a, team_b)
    std_dev = 11.0
    return float(norm.cdf(diff / std_dev))


def simulate_game(team_a: Team, team_b: Team, locked_winner: Optional[str] = None) -> Team:
    """
    Simulate a single game. If locked_winner is set, return that team.
    Otherwise, draw a random outcome based on win probability.
    """
    if locked_winner:
        return team_a if team_a.name == locked_winner else team_b

    p_a = win_probability(team_a, team_b)
    return team_a if random.random() < p_a else team_b


# ---------------------------------------------------------------------------
# Single tournament simulation
# ---------------------------------------------------------------------------

def simulate_tournament(
    teams_by_region: dict[str, dict[int, Team]],
    locked_results: dict[str, str],   # game_id -> winning team name
) -> dict[str, list[str]]:
    """
    Simulate one full tournament. Returns a dict mapping each team name
    to the list of round names they reached (e.g. ["R64", "R32", "S16"]).
    """
    # advancement[team_name] = highest round reached (as round number)
    advancement: dict[str, int] = {}

    def play(team_a: Team, team_b: Team, game_id: str) -> Team:
        locked = locked_results.get(game_id)
        winner = simulate_game(team_a, team_b, locked)
        return winner

    region_winners: dict[str, Team] = {}

    for region in REGIONS:
        seed_map = teams_by_region[region]

        # Round 1
        r1_winners: list[Team] = []
        for i, (s_a, s_b) in enumerate(FIRST_ROUND_MATCHUPS):
            gid = f"{region}_R1_G{i+1}"
            t_a, t_b = seed_map[s_a], seed_map[s_b]
            # Both teams have reached at least R64
            advancement.setdefault(t_a.name, 1)
            advancement.setdefault(t_b.name, 1)
            w = play(t_a, t_b, gid)
            advancement[w.name] = max(advancement.get(w.name, 0), 2)
            r1_winners.append(w)

        # Round 2
        r2_winners: list[Team] = []
        for i, (a, b) in enumerate(ROUND2_PAIRS):
            gid = f"{region}_R2_G{i+1}"
            w = play(r1_winners[a], r1_winners[b], gid)
            advancement[w.name] = max(advancement.get(w.name, 0), 3)
            r2_winners.append(w)

        # Round 3 (Sweet 16)
        r3_winners: list[Team] = []
        for i, (a, b) in enumerate(ROUND3_PAIRS):
            gid = f"{region}_R3_G{i+1}"
            w = play(r2_winners[a], r2_winners[b], gid)
            advancement[w.name] = max(advancement.get(w.name, 0), 4)
            r3_winners.append(w)

        # Round 4 (Elite 8)
        gid = f"{region}_R4_G1"
        region_champ = play(r3_winners[0], r3_winners[1], gid)
        advancement[region_champ.name] = max(advancement.get(region_champ.name, 0), 5)
        region_winners[region] = region_champ

    # Final Four
    ff_winners: list[Team] = []
    for i, (r_a, r_b) in enumerate(FINAL_FOUR_PAIRS):
        gid = f"FF_G{i+1}"
        w = play(region_winners[r_a], region_winners[r_b], gid)
        advancement[w.name] = max(advancement.get(w.name, 0), 6)
        ff_winners.append(w)

    # Championship
    champion = play(ff_winners[0], ff_winners[1], "Championship")
    advancement[champion.name] = max(advancement.get(champion.name, 0), 7)

    return advancement


# ---------------------------------------------------------------------------
# Monte Carlo runner
# ---------------------------------------------------------------------------

ROUND_LABELS = {
    1: "R64",
    2: "R32",
    3: "S16",
    4: "E8",
    5: "FF",
    6: "Championship",
    7: "Champion",
}


def run_monte_carlo(
    teams: dict[str, Team],
    n_simulations: int = 10_000,
    locked_results: Optional[dict[str, str]] = None,
) -> dict:
    """
    Run N full tournament simulations and aggregate results.

    Returns:
    {
        "n_simulations": 10000,
        "teams": {
            "Duke": {
                "seed": 1, "region": "East",
                "adj_em": 28.4, "adj_o": 118.2, "adj_d": 89.8, "adj_t": 71.3,
                "advancement": {
                    "R64": 1.0, "R32": 0.84, "S16": 0.61,
                    "E8": 0.41, "FF": 0.22, "Championship": 0.11, "Champion": 0.05
                }
            },
            ...
        },
        "matchups": {
            "East_R1_G1": {
                "round": 1, "region": "East",
                "team_a": "Duke", "team_b": "UCSB",
                "win_prob_a": 0.94, "win_prob_b": 0.06,
                "point_diff": 18.2,
                "locked_winner": null
            },
            ...
        }
    }
    """
    if locked_results is None:
        locked_results = {}

    # Build seed maps per region
    teams_by_region: dict[str, dict[int, Team]] = {r: {} for r in REGIONS}
    for team in teams.values():
        if team.region in teams_by_region:
            teams_by_region[team.region][team.seed] = team

    # Accumulate advancement counts
    # advancement_counts[team_name][round_num] = number of times reached
    advancement_counts: dict[str, dict[int, int]] = {
        name: defaultdict(int) for name in teams
    }

    for _ in range(n_simulations):
        result = simulate_tournament(teams_by_region, locked_results)
        for team_name, max_round in result.items():
            # A team reaching round R means they also reached all prior rounds
            for r in range(1, max_round + 1):
                advancement_counts[team_name][r] += 1

    # Build output
    teams_out = {}
    for name, team in teams.items():
        adv = {}
        for r, label in ROUND_LABELS.items():
            count = advancement_counts[name].get(r, 0)
            adv[label] = round(count / n_simulations, 4)
        teams_out[name] = {
            "seed": team.seed,
            "region": team.region,
            "adj_em": team.adj_em,
            "adj_o": team.adj_o,
            "adj_d": team.adj_d,
            "adj_t": team.adj_t,
            "advancement": adv,
        }

    # Build matchup-level data (first round only has known teams;
    # later rounds we compute based on expected opponents)
    matchups_out = build_matchup_summary(teams_by_region, locked_results)

    return {
        "n_simulations": n_simulations,
        "teams": teams_out,
        "matchups": matchups_out,
    }


def build_matchup_summary(
    teams_by_region: dict[str, dict[int, Team]],
    locked_results: dict[str, str],
) -> dict:
    """
    Build matchup data for ALL rounds based on locked/actual results.
    Round 1 always has known matchups. Later rounds are built by
    simulating forward through the locked results.
    """
    matchups = {}

    for region in REGIONS:
        seed_map = teams_by_region[region]

        # Build round-by-round winners using locked results
        # round_teams[r] = list of Team objects playing in round r
        round_teams = {}
        round_teams[1] = [seed_map[s] for s in [seed for pair in FIRST_ROUND_MATCHUPS for seed in pair]]

        for r in range(1, 5):
            prev = round_teams[r]
            next_round = []
            for game_idx in range(len(prev) // 2):
                gid = f"{region}_R{r}_G{game_idx + 1}"
                t_a = prev[game_idx * 2]
                t_b = prev[game_idx * 2 + 1]
                locked_name = locked_results.get(gid)
                if locked_name:
                    winner = t_a if t_a.name == locked_name else t_b
                else:
                    winner = None  # unknown
                next_round.append(winner)
            round_teams[r + 1] = next_round

        # Build matchup entries for all rounds
        for r in range(1, 5):
            teams_in_round = round_teams[r]
            seeds_in_round = []
            if r == 1:
                seeds_in_round = [s for pair in FIRST_ROUND_MATCHUPS for s in pair]
            
            for game_idx in range(len(teams_in_round) // 2):
                gid = f"{region}_R{r}_G{game_idx + 1}"
                t_a = teams_in_round[game_idx * 2]
                t_b = teams_in_round[game_idx * 2 + 1]

                if t_a is None or t_b is None:
                    continue  # unknown matchup — both teams not yet determined

                diff = point_differential(t_a, t_b)
                prob_a = win_probability(t_a, t_b)

                if r == 1:
                    s_a = seeds_in_round[game_idx * 2]
                    s_b = seeds_in_round[game_idx * 2 + 1]
                else:
                    s_a = t_a.seed
                    s_b = t_b.seed

                is_upset_alert = (
                    (s_a > s_b and prob_a > 0.40) or
                    (s_b > s_a and (1 - prob_a) > 0.40)
                )

                matchups[gid] = {
                    "round": r,
                    "region": region,
                    "team_a": t_a.name,
                    "team_b": t_b.name,
                    "seed_a": s_a,
                    "seed_b": s_b,
                    "win_prob_a": round(prob_a, 4),
                    "win_prob_b": round(1 - prob_a, 4),
                    "point_diff": round(diff, 2),
                    "locked_winner": locked_results.get(gid),
                    "upset_alert": is_upset_alert,
                }

    return matchups
