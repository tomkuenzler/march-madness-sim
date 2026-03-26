"""
espn_sync.py

Fetches completed NCAA Tournament game results from ESPN's unofficial API
and maps them to our internal game ID format (e.g. East_R1_G1).

ESPN endpoint:
  https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard
  ?dates=YYYYMMDD-YYYYMMDD&groups=100&limit=200

groups=100 filters to NCAA Tournament games only.

Game ID format: {Region}_{RoundKey}_{GameNum}
  Region:   East, West, South, Midwest
  RoundKey: R1, R2, R3, R4 (regional), FF (Final Four), Championship
  GameNum:  G1-G8 for R1, G1-G4 for R2, G1-G2 for R3, G1 for R4/FF

Seed-to-game mapping per region (top to bottom):
  R1: G1=1v16, G2=8v9, G3=5v12, G4=4v13, G5=6v11, G6=3v14, G7=7v10, G8=2v15
"""

import requests
from datetime import datetime, timedelta
from typing import Optional

ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball"
    "/mens-college-basketball/scoreboard"
)

# Tournament dates for 2026
TOURNAMENT_DATE_RANGES = [
    ("20260317", "20260318"),  # First Four
    ("20260319", "20260320"),  # First Round
    ("20260321", "20260322"),  # Second Round
    ("20260326", "20260327"),  # Sweet 16
    ("20260328", "20260329"),  # Elite Eight
    ("20260404", "20260404"),  # Final Four
    ("20260406", "20260406"),  # Championship
]

# ESPN round name -> our round key
ROUND_NAME_MAP = {
    "first four":    None,        # skip First Four
    "1st round":     "R1",
    "first round":   "R1",
    "2nd round":     "R2",
    "second round":  "R2",
    "sweet 16":      "R3",
    "elite eight":   "R4",
    "elite 8":       "R4",
    "final four":    "FF",
    "national championship": "Championship",
    "championship":  "Championship",
}

# Seed pair -> game number within a region (R1 only)
# Key: frozenset of the two seeds, Value: game number (1-indexed)
R1_SEED_TO_GAME = {
    frozenset({1, 16}): 1,
    frozenset({8, 9}):  2,
    frozenset({5, 12}): 3,
    frozenset({4, 13}): 4,
    frozenset({6, 11}): 5,
    frozenset({3, 14}): 6,
    frozenset({7, 10}): 7,
    frozenset({2, 15}): 8,
}

# For R2-R4 we derive game number from the seed of the winner
# R2 matchups (winners of R1 games play each other):
# G1 = winner of G1 vs winner of G2 (seeds 1/16 vs 8/9)
# G2 = winner of G3 vs winner of G4 (seeds 5/12 vs 4/13)
# G3 = winner of G5 vs winner of G6 (seeds 6/11 vs 3/14)
# G4 = winner of G7 vs winner of G8 (seeds 7/10 vs 2/15)
# We detect this by looking at which "bracket half" the seeds belong to

def seeds_to_r2_game(seed_a: int, seed_b: int) -> int:
    """Map two seeds to R2 game number based on bracket position."""
    pair = frozenset({seed_a, seed_b})
    # Top half of bracket: seeds from G1+G2 area vs G3+G4 area
    top_seeds = {1, 16, 8, 9, 5, 12, 4, 13}
    bottom_seeds = {6, 11, 3, 14, 7, 10, 2, 15}
    
    if seed_a in {1, 16, 8, 9} or seed_b in {1, 16, 8, 9}:
        return 1  # G1 vs G2 winners
    if seed_a in {5, 12, 4, 13} or seed_b in {5, 12, 4, 13}:
        return 2  # G3 vs G4 winners
    if seed_a in {6, 11, 3, 14} or seed_b in {6, 11, 3, 14}:
        return 3  # G5 vs G6 winners
    return 4  # G7 vs G8 winners (seeds 7/10/2/15)


def seeds_to_r3_game(seed_a: int, seed_b: int) -> int:
    """Map two seeds to R3 (Sweet 16) game number."""
    # Top half of region vs bottom half
    if min(seed_a, seed_b) <= 4:
        # Could be G1 (top half) or G2 (bottom half)
        top = {1, 16, 8, 9, 5, 12, 4, 13}
        if seed_a in top or seed_b in top:
            return 1
    return 2


# ESPN team name -> our KenPom team name
# Only needed for names that differ between ESPN and KenPom
ESPN_NAME_MAP = {
    # Connecticut
    "UConn":                    "Connecticut",
    "UConn Huskies":            "Connecticut",
    "Connecticut Huskies":      "Connecticut",
    # Saint Mary's
    "Saint Mary's (CA)":        "Saint Mary's",
    "Saint Mary's Gaels":       "Saint Mary's",
    # Miami FL
    "Miami":                    "Miami FL",
    "Miami (FL)":               "Miami FL",
    "Miami Hurricanes":         "Miami FL",
    # Iowa State
    "Iowa State":               "Iowa St.",
    "Iowa State Cyclones":      "Iowa St.",
    # Michigan State
    "Michigan State":           "Michigan St.",
    "Michigan State Spartans":  "Michigan St.",
    # St. John's
    "St. John's (NY)":          "St. John's",
    "St. John's Red Storm":     "St. John's",
    # Utah State
    "Utah State":               "Utah St.",
    "Utah State Aggies":        "Utah St.",
    # Miami Ohio
    "Miami (Ohio)":             "Miami OH",
    "Miami (OH)":               "Miami OH",
    "Miami RedHawks":           "Miami OH",
    # LIU
    "Long Island University":   "LIU",
    "LIU Sharks":               "LIU",
    # Queens
    "Queens (NC)":              "Queens",
    "Queens Royals":            "Queens",
    # Hawaii
    "Hawaii":                   "Hawaii",
    "Hawai'i":                  "Hawaii",
    "Hawaii Rainbow Warriors":  "Hawaii",
    # Tennessee State
    "Tennessee State":          "Tennessee St.",
    "Tennessee State Tigers":   "Tennessee St.",
    #Texas Tech
    "Texas Tech Red Raiders":   "Texas Tech",
    # North Dakota State
    "North Dakota St.":         "North Dakota St.",
    "North Dakota State":       "North Dakota St.",
    "North Dakota State Bison": "North Dakota St.",
    # Wright State
    "Wright State":             "Wright St.",
    "Wright State Raiders":     "Wright St.",
    # Kennesaw State
    "Kennesaw State":           "Kennesaw St.",
    "Kennesaw State Owls":      "Kennesaw St.",
    # Prairie View
    "Prairie View":             "Prairie View A&M",
    "Prairie View A&M Panthers":"Prairie View A&M",
    # Cal Baptist
    "Cal Baptist Lancers":      "Cal Baptist",
    # Texas A&M
    "Texas A&M Aggies":         "Texas A&M",
    # North Carolina
    "North Carolina Tar Heels": "North Carolina",
    # VCU
    "VCU Rams":                 "VCU",
    # Saint Louis
    "Saint Louis Billikens":    "Saint Louis",
    # Gonzaga
    "Gonzaga Bulldogs":         "Gonzaga",
    # Houston
    "Houston Cougars":          "Houston",
    # Virginia
    "Virginia Cavaliers":       "Virginia",
    # Arkansas
    "Arkansas Razorbacks":      "Arkansas",
    # Illinois
    "Illinois Fighting Illini": "Illinois",
    # Nebraska
    "Nebraska Cornhuskers":     "Nebraska",
    # Alabama
    "Alabama Crimson Tide":     "Alabama",
    # Tennessee
    "Tennessee Volunteers":     "Tennessee",
    # Kentucky
    "Kentucky Wildcats":        "Kentucky",
    # Iowa
    "Iowa Hawkeyes":            "Iowa",
    # Purdue
    "Purdue Boilermakers":      "Purdue",
    # Connecticut (duplicate safety)
    "Saint Mary's":             "Saint Mary's",
    "SMU":                      "SMU",
    "Texas A&M":                "Texas A&M",
    "Prairie View A&M":         "Prairie View A&M",
    "North Dakota St.":         "North Dakota St.",
    "Cal Baptist":              "Cal Baptist",
    "LIU":                      "LIU",
    "Hawaii":                   "Hawaii",
    "North Carolina":           "North Carolina",
    "Howard":                   "Howard",
    "High Point":               "High Point",
    "Northern Iowa":            "Northern Iowa",
}


def normalize_team_name(espn_name: str, known_teams: set[str]) -> str:
    """Map ESPN team name to our internal name."""
    # Direct lookup in map
    if espn_name in ESPN_NAME_MAP:
        mapped = ESPN_NAME_MAP[espn_name]
        if mapped in known_teams:
            return mapped

    # Already matches
    if espn_name in known_teams:
        return espn_name

    # Try stripping common suffixes
    for suffix in [" Huskies", " Wolverines", " Wildcats", " Bulldogs",
                   " Cardinals", " Eagles", " Tigers", " Bears"]:
        stripped = espn_name.replace(suffix, "")
        if stripped in known_teams:
            return stripped

    # Fuzzy: find closest match
    espn_lower = espn_name.lower()
    for known in known_teams:
        if known.lower() in espn_lower or espn_lower in known.lower():
            return known

    return espn_name  # return as-is if no match found


def parse_round_key(notes: list) -> Optional[str]:
    """Extract round key from ESPN game notes."""
    for note in notes:
        headline = note.get("headline", "").lower()
        for key, round_key in ROUND_NAME_MAP.items():
            if key in headline:
                return round_key
    return None


def parse_region(notes: list, competitors: list) -> Optional[str]:
    for note in notes:
        headline = note.get("headline", "")
        # IMPORTANT: check Midwest before West since West is a substring of Midwest
        for region in ["Midwest", "East", "West", "South"]:
            if f"{region} Region" in headline:
                return region
        # Fallback
        for region in ["Midwest", "East", "West", "South"]:
            if region.lower() in headline.lower():
                return region
    return None


def build_game_id(
    round_key: str,
    region: Optional[str],
    seed_a: int,
    seed_b: int,
    ff_game_num: Optional[int] = None,
) -> Optional[str]:
    """Build our internal game ID from round, region, and seeds."""
    if round_key == "Championship":
        return "Championship"

    if round_key == "FF":
        # FF games: G1 = East vs South, G2 = West vs Midwest
        # We can't always determine this from seeds alone, so use ff_game_num
        if ff_game_num:
            return f"FF_G{ff_game_num}"
        return None

    if not region:
        return None

    if round_key == "R1":
        game_num = R1_SEED_TO_GAME.get(frozenset({seed_a, seed_b}))
        if game_num:
            return f"{region}_R1_G{game_num}"

    if round_key == "R2":
        game_num = seeds_to_r2_game(seed_a, seed_b)
        return f"{region}_R2_G{game_num}"

    if round_key == "R3":
        game_num = seeds_to_r3_game(seed_a, seed_b)
        return f"{region}_R3_G{game_num}"

    if round_key == "R4":
        return f"{region}_R4_G1"

    return None


def fetch_espn_results(
    known_teams: set[str],
    existing_results: dict[str, str],
) -> dict[str, str]:
    """
    Fetch all completed NCAA Tournament games from ESPN and return
    a dict of {game_id: winner_name} for completed games only.

    Merges with existing_results — won't overwrite existing entries.
    """
    new_results = dict(existing_results)
    ff_game_counter = [0]  # track FF game ordering

    for start_date, end_date in TOURNAMENT_DATE_RANGES:
        try:
            params = {
                "dates": f"{start_date}-{end_date}",
                "groups": "100",
                "limit": "200",
            }
            resp = requests.get(ESPN_SCOREBOARD, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[ESPN] Error fetching {start_date}-{end_date}: {e}")
            continue

        events = data.get("events", [])
        print(f"[ESPN] {start_date}-{end_date}: {len(events)} events")

        for event in events:
            competitions = event.get("competitions", [])
            if not competitions:
                continue

            comp = competitions[0]
            notes = comp.get("notes", []) or event.get("notes", [])

            # Only process completed games
            status = comp.get("status", {})
            if not status.get("type", {}).get("completed", False):
                continue

            round_key = parse_round_key(notes)
            if round_key is None:
                continue  # skip non-tournament or First Four

            region = parse_region(notes, comp.get("competitors", []))
            competitors = comp.get("competitors", [])

            if len(competitors) != 2:
                continue

            # Extract team info
            teams_info = []
            for c in competitors:
                team = c.get("team", {})
                name = normalize_team_name(
                    team.get("displayName", team.get("shortDisplayName", "")),
                    known_teams
                )
                seed_str = c.get("curatedRank", {}).get("current") or c.get("seed")
                try:
                    seed = int(seed_str) if seed_str else 0
                except (ValueError, TypeError):
                    seed = 0
                winner = c.get("winner", False)
                teams_info.append({"name": name, "seed": seed, "winner": winner})

            # Find winner
            winners = [t for t in teams_info if t["winner"]]
            if not winners:
                continue
            winner_name = winners[0]["name"]

            seed_a = teams_info[0]["seed"]
            seed_b = teams_info[1]["seed"]

            # Handle Final Four game numbering
            ff_game_num = None
            if round_key == "FF":
                ff_game_counter[0] += 1
                ff_game_num = ff_game_counter[0]

            game_id = build_game_id(round_key, region, seed_a, seed_b, ff_game_num)

            if not game_id:
                print(f"[ESPN] Could not build game ID for {teams_info[0]['name']} vs {teams_info[1]['name']} ({round_key}, {region})")
                continue

            if game_id not in new_results:
                new_results[game_id] = winner_name
                print(f"[ESPN] {game_id} -> {winner_name}")
            else:
                # Verify consistency
                if new_results[game_id] != winner_name:
                    print(f"[ESPN] WARNING: {game_id} mismatch — stored={new_results[game_id]}, espn={winner_name}")

    return new_results
