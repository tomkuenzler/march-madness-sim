"""
espn_sync.py

Fetches completed NCAA Tournament game results and scores from ESPN's unofficial API
and maps them to our internal game ID format (e.g. East_R1_G1).

Returns both results (game_id -> winner) and scores (game_id -> "W_score-L_score")
"""

import requests
from typing import Optional

ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball"
    "/mens-college-basketball/scoreboard"
)

TOURNAMENT_DATE_RANGES = [
    ("20260317", "20260318"),  # First Four
    ("20260319", "20260320"),  # First Round
    ("20260321", "20260322"),  # Second Round
    ("20260326", "20260327"),  # Sweet 16
    ("20260328", "20260329"),  # Elite Eight
    ("20260404", "20260404"),  # Final Four
    ("20260406", "20260406"),  # Championship
]

ROUND_NAME_MAP = {
    "first four":            None,
    "1st round":             "R1",
    "first round":           "R1",
    "2nd round":             "R2",
    "second round":          "R2",
    "sweet 16":              "R3",
    "elite eight":           "R4",
    "elite 8":               "R4",
    "final four":            "FF",
    "national championship": "Championship",
    "championship":          "Championship",
}

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

ESPN_NAME_MAP = {
    "UConn":                     "Connecticut",
    "UConn Huskies":             "Connecticut",
    "Connecticut Huskies":       "Connecticut",
    "Saint Mary's (CA)":         "Saint Mary's",
    "Saint Mary's Gaels":        "Saint Mary's",
    "Miami":                     "Miami FL",
    "Miami (FL)":                "Miami FL",
    "Miami Hurricanes":          "Miami FL",
    "Iowa State":                "Iowa St.",
    "Iowa State Cyclones":       "Iowa St.",
    "Michigan State":            "Michigan St.",
    "Michigan State Spartans":   "Michigan St.",
    "St. John's (NY)":           "St. John's",
    "St. John's Red Storm":      "St. John's",
    "Utah State":                "Utah St.",
    "Utah State Aggies":         "Utah St.",
    "Miami (Ohio)":              "Miami OH",
    "Miami (OH)":                "Miami OH",
    "Miami RedHawks":            "Miami OH",
    "Long Island University":    "LIU",
    "LIU Sharks":                "LIU",
    "Queens (NC)":               "Queens",
    "Queens Royals":             "Queens",
    "Hawaii":                    "Hawaii",
    "Hawai'i":                   "Hawaii",
    "Hawaii Rainbow Warriors":   "Hawaii",
    "Tennessee State":           "Tennessee St.",
    "Tennessee State Tigers":    "Tennessee St.",
    "North Dakota St.":          "North Dakota St.",
    "North Dakota State":        "North Dakota St.",
    "North Dakota State Bison":  "North Dakota St.",
    "Wright State":              "Wright St.",
    "Wright State Raiders":      "Wright St.",
    "Kennesaw State":            "Kennesaw St.",
    "Kennesaw State Owls":       "Kennesaw St.",
    "Prairie View":              "Prairie View A&M",
    "Prairie View A&M Panthers": "Prairie View A&M",
    "Cal Baptist Lancers":       "Cal Baptist",
    "Texas A&M Aggies":          "Texas A&M",
    "North Carolina Tar Heels":  "North Carolina",
    "VCU Rams":                  "VCU",
    "Saint Louis Billikens":     "Saint Louis",
    "Gonzaga Bulldogs":          "Gonzaga",
    "Houston Cougars":           "Houston",
    "Virginia Cavaliers":        "Virginia",
    "Arkansas Razorbacks":       "Arkansas",
    "Illinois Fighting Illini":  "Illinois",
    "Nebraska Cornhuskers":      "Nebraska",
    "Alabama Crimson Tide":      "Alabama",
    "Tennessee Volunteers":      "Tennessee",
    "Kentucky Wildcats":         "Kentucky",
    "Iowa Hawkeyes":             "Iowa",
    "Purdue Boilermakers":       "Purdue",
    "Texas Tech Red Raiders":    "Texas Tech",
    "Northern Iowa Panthers":    "Northern Iowa",
    "Akron Zips":                "Akron",
    "McNeese Cowboys":           "McNeese",
    "Troy Trojans":              "Troy",
    "Pennsylvania Quakers":      "Penn",
    "Idaho Vandals":             "Idaho",
    "Siena Saints":              "Siena",
    "Furman Paladins":           "Furman",
    "Howard Bison":              "Howard",
    "South Florida Bulls":       "South Florida",
    "TCU Horned Frogs":          "TCU",
    "UCF Knights":               "UCF",
    "Georgia Bulldogs":          "Georgia",
    "Villanova Wildcats":        "Villanova",
    "Missouri Tigers":           "Missouri",
    "Santa Clara Broncos":       "Santa Clara",
    "Clemson Tigers":            "Clemson",
    "BYU Cougars":               "BYU",
    "Louisville Cardinals":      "Louisville",
    "Kansas Jayhawks":           "Kansas",
    "UCLA Bruins":               "UCLA",
    "Duke Blue Devils":          "Duke",
    "Florida Gators":            "Florida",
    "Arizona Wildcats":          "Arizona",
    "Michigan Wolverines":       "Michigan",
    "Ohio State Buckeyes":       "Ohio St.",
    "Wisconsin Badgers":         "Wisconsin",
    "High Point Panthers":       "High Point",
}


def normalize_team_name(espn_name: str, known_teams: set) -> str:
    if espn_name in ESPN_NAME_MAP:
        mapped = ESPN_NAME_MAP[espn_name]
        if mapped in known_teams:
            return mapped
    if espn_name in known_teams:
        return espn_name
    # Sort by length descending to match longer names first
    sorted_known = sorted(known_teams, key=len, reverse=True)
    espn_lower = espn_name.lower()
    for known in sorted_known:
        if known.lower() == espn_lower:
            return known
        if (known.lower() in espn_lower or espn_lower in known.lower()):
            if abs(len(known) - len(espn_name)) <= 3:
                return known
    return espn_name


def parse_round_key(notes: list) -> Optional[str]:
    for note in notes:
        headline = note.get("headline", "").lower()
        for key, round_key in ROUND_NAME_MAP.items():
            if key in headline:
                return round_key
    return None


def parse_region(notes: list) -> Optional[str]:
    for note in notes:
        headline = note.get("headline", "")
        # Check Midwest before West — West is a substring of Midwest
        for region in ["Midwest", "East", "West", "South"]:
            if f"{region} Region" in headline:
                return region
        headline_lower = headline.lower()
        for region in ["Midwest", "East", "West", "South"]:
            if region.lower() in headline_lower:
                return region
    return None


def seeds_to_r2_game(seed_a: int, seed_b: int) -> int:
    if seed_a in {1, 16, 8, 9} or seed_b in {1, 16, 8, 9}:
        return 1
    if seed_a in {5, 12, 4, 13} or seed_b in {5, 12, 4, 13}:
        return 2
    if seed_a in {6, 11, 3, 14} or seed_b in {6, 11, 3, 14}:
        return 3
    return 4


def seeds_to_r3_game(seed_a: int, seed_b: int) -> int:
    top = {1, 16, 8, 9, 5, 12, 4, 13}
    if seed_a in top or seed_b in top:
        return 1
    return 2


def build_game_id(
    round_key: str,
    region: Optional[str],
    seed_a: int,
    seed_b: int,
    ff_game_num: Optional[int] = None,
) -> Optional[str]:
    if round_key == "Championship":
        return "Championship"
    if round_key == "FF":
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
        return f"{region}_R2_G{seeds_to_r2_game(seed_a, seed_b)}"
    if round_key == "R3":
        return f"{region}_R3_G{seeds_to_r3_game(seed_a, seed_b)}"
    if round_key == "R4":
        return f"{region}_R4_G1"
    return None


def fetch_espn_results(
    known_teams: set,
    existing_results: dict,
    existing_scores: dict = None,
) -> tuple:
    """
    Fetch all completed NCAA Tournament games from ESPN.
    Returns (results_dict, scores_dict).
    results: {game_id: winner_name}
    scores:  {game_id: "winner_score-loser_score"}
    """
    new_results = dict(existing_results)
    new_scores = dict(existing_scores or {})
    ff_game_counter = [0]

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
            if not comp.get("status", {}).get("type", {}).get("completed", False):
                continue

            round_key = parse_round_key(notes)
            if round_key is None:
                continue

            region = parse_region(notes)
            competitors = comp.get("competitors", [])
            if len(competitors) != 2:
                continue

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
                score = c.get("score", "")
                teams_info.append({
                    "name": name, "seed": seed,
                    "winner": winner, "score": score
                })

            winners = [t for t in teams_info if t["winner"]]
            if not winners:
                continue
            winner_info = winners[0]
            loser_info = [t for t in teams_info if not t["winner"]][0]
            winner_name = winner_info["name"]

            seed_a = teams_info[0]["seed"]
            seed_b = teams_info[1]["seed"]

            ff_game_num = None
            if round_key == "FF":
                ff_game_counter[0] += 1
                ff_game_num = ff_game_counter[0]

            game_id = build_game_id(round_key, region, seed_a, seed_b, ff_game_num)

            if not game_id:
                print(f"[ESPN] Could not build game ID for {teams_info[0]['name']} vs {teams_info[1]['name']} ({round_key}, {region})")
                continue

            # Store score as "winner_score-loser_score"
            w_score = winner_info.get("score", "")
            l_score = loser_info.get("score", "")
            score_str = f"{w_score}-{l_score}" if w_score and l_score else ""

            if game_id not in new_results:
                new_results[game_id] = winner_name
                if score_str:
                    new_scores[game_id] = score_str
                print(f"[ESPN] {game_id} -> {winner_name} {score_str}")
            else:
                if new_results[game_id] != winner_name:
                    print(f"[ESPN] WARNING: {game_id} mismatch — stored={new_results[game_id]}, espn={winner_name}")
                # Update score even if result already stored
                if score_str and game_id not in new_scores:
                    new_scores[game_id] = score_str

    return new_results, new_scores
