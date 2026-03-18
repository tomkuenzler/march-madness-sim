"""
bracket.py
Builds the NCAA Tournament bracket structure from KenPom CSV data.
Handles seeding logic, region assignment, and matchup generation.
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class Team:
    name: str
    seed: int
    region: str
    adj_em: float      # Net Rating (KenPom AdjEM)
    adj_o: float       # Offensive efficiency
    adj_d: float       # Defensive efficiency
    adj_t: float       # Tempo


@dataclass
class Game:
    game_id: str
    round_num: int          # 1=R64, 2=R32, 3=Sweet16, 4=Elite8, 5=Final4, 6=Championship
    region: str             # "Final Four" for rounds 5-6
    team_a: Optional[Team] = None
    team_b: Optional[Team] = None
    locked_winner: Optional[str] = None   # team name if manually locked


# Standard NCAA bracket: 1 plays 16, 2 plays 15, etc.
FIRST_ROUND_MATCHUPS = [(1, 16), (8, 9), (5, 12), (4, 13), (6, 11), (3, 14), (7, 10), (2, 15)]

# Bracket progression: which seed matchup winners meet in round 2
# Slot indices (0-7) represent the 8 first-round games per region
ROUND2_PAIRS = [(0, 1), (2, 3), (4, 5), (6, 7)]
ROUND3_PAIRS = [(0, 1), (2, 3)]
ROUND4_PAIRS = [(0, 1)]

REGIONS = ["East", "West", "South", "Midwest"]

# Final Four matchups: East vs West, South vs Midwest (standard NCAA)
FINAL_FOUR_PAIRS = [("East", "West"), ("South", "Midwest")]

ROUND_NAMES = {
    1: "Round of 64",
    2: "Round of 32",
    3: "Sweet 16",
    4: "Elite 8",
    5: "Final Four",
    6: "Championship",
}


def load_teams_from_csv(filepath: str) -> dict[str, Team]:
    """Load and validate KenPom CSV. Returns dict keyed by team name."""
    df = pd.read_csv(filepath)

    # Normalize column names: strip whitespace, handle common variants
    df.columns = df.columns.str.strip()
    col_map = {
        "AdjEM": "adj_em", "NetRTG": "adj_em", "adjem": "adj_em",
        "AdjO": "adj_o", "OE": "adj_o", "adjo": "adj_o",
        "AdjD": "adj_d", "DE": "adj_d", "adjd": "adj_d",
        "AdjT": "adj_t", "Tempo": "adj_t", "adjt": "adj_t",
        "Team": "name", "team": "name",
        "Seed": "seed", "seed": "seed",
        "Region": "region", "region": "region",
    }
    # Lowercase the columns first, then map
    df.columns = [col_map.get(c, col_map.get(c.lower(), c)) for c in df.columns]

    required = ["name", "adj_em", "adj_o", "adj_d", "adj_t", "seed", "region"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    # Only keep tournament teams (seed 1-16, valid region)
    df["region"] = df["region"].str.title()
    df = df[df["region"].isin(REGIONS)].copy()
    df["seed"] = df["seed"].astype(int)

    teams = {}
    for _, row in df.iterrows():
        team = Team(
            name=str(row["name"]).strip(),
            seed=int(row["seed"]),
            region=str(row["region"]).strip(),
            adj_em=float(row["adj_em"]),
            adj_o=float(row["adj_o"]),
            adj_d=float(row["adj_d"]),
            adj_t=float(row["adj_t"]),
        )
        teams[team.name] = team

    return teams


def build_bracket(teams: dict[str, Team]) -> list[Game]:
    """
    Constructs the full 63-game bracket shell.
    Returns a flat list of Game objects in round order.
    Games without assigned teams are placeholders for later rounds.
    """
    games: list[Game] = []

    # Group teams by region
    by_region: dict[str, list[Team]] = {r: [] for r in REGIONS}
    for team in teams.values():
        if team.region in by_region:
            by_region[team.region].append(team)

    # Validate: each region should have exactly 16 teams
    for region, region_teams in by_region.items():
        if len(region_teams) != 16:
            raise ValueError(
                f"Region '{region}' has {len(region_teams)} teams, expected 16. "
                "Check your CSV seed/region columns."
            )

    # Build regional rounds (1-4)
    for region in REGIONS:
        region_teams = by_region[region]
        seed_map = {t.seed: t for t in region_teams}

        # Round 1: 8 games per region
        r1_games = []
        for i, (s_a, s_b) in enumerate(FIRST_ROUND_MATCHUPS):
            game = Game(
                game_id=f"{region}_R1_G{i+1}",
                round_num=1,
                region=region,
                team_a=seed_map[s_a],
                team_b=seed_map[s_b],
            )
            r1_games.append(game)
            games.append(game)

        # Round 2: 4 games per region
        r2_games = []
        for i, (a, b) in enumerate(ROUND2_PAIRS):
            game = Game(
                game_id=f"{region}_R2_G{i+1}",
                round_num=2,
                region=region,
            )
            r2_games.append(game)
            games.append(game)

        # Round 3 (Sweet 16): 2 games per region
        r3_games = []
        for i, (a, b) in enumerate(ROUND3_PAIRS):
            game = Game(
                game_id=f"{region}_R3_G{i+1}",
                round_num=3,
                region=region,
            )
            r3_games.append(game)
            games.append(game)

        # Round 4 (Elite 8): 1 game per region
        elite8_game = Game(
            game_id=f"{region}_R4_G1",
            round_num=4,
            region=region,
        )
        games.append(elite8_game)

    # Final Four: 2 games
    for i, (r_a, r_b) in enumerate(FINAL_FOUR_PAIRS):
        game = Game(
            game_id=f"FF_G{i+1}",
            round_num=5,
            region="Final Four",
        )
        games.append(game)

    # Championship: 1 game
    games.append(Game(
        game_id="Championship",
        round_num=6,
        region="Final Four",
    ))

    return games


def get_round_name(round_num: int) -> str:
    return ROUND_NAMES.get(round_num, f"Round {round_num}")
