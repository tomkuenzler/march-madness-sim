/**
 * bracketLayout.js
 *
 * KEY MENTAL MODEL:
 *
 * roundSlots[r][i] = team OCCUPYING slot i in round r display.
 * locked["Region_R{r}_G{i}"] = winner of that game → appears in round r+1 slot i.
 *
 * Regional rounds 1-5 (R64 through FF) are built per region.
 * Championship round (round 6) is built from the two FF winners.
 *
 * FF_G1: East FF winner vs West FF winner  → champion slot left
 * FF_G2: South FF winner vs Midwest FF winner → champion slot right
 * Championship: FF_G1 winner vs FF_G2 winner → champion
 */

export const SVG_WIDTH  = 1800;
export const SVG_HEIGHT = 880; // slightly taller to fit championship below FF
export const SLOT_W = 148;
export const SLOT_H = 28;

// 1-indexed regional rounds: [0] unused, [1]=R1 ... [5]=FF
export const LEFT_ROUND_X  = [0,  10,  220, 400, 570, 730];
export const RIGHT_ROUND_X = [0, 1642, 1432, 1252, 1082, 922];

// Championship game slots — side by side in center
// Left finalist (East/South winner): same x as left FF
// Right finalist (West/Midwest winner): same x as right FF
export const CHAMP_LEFT_X  = 730;   // left finalist slot x
export const CHAMP_RIGHT_X = 922;   // right finalist slot x
export const CHAMP_Y       = 410;   // y position of finalist slots
export const CHAMPION_X    = 826;   // champion box x (centered between finalists)
export const CHAMPION_Y    = 468;   // champion box y (below finalist slots)

export const LEFT_SPINE_X  = 645;
export const RIGHT_SPINE_X = 1155;

export const REGIONS = ['East', 'South', 'West', 'Midwest'];
export const SEED_ORDER = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15];

// What round do you reach by winning game in round R?
export const ROUND_ADV_KEYS = {
  1: 'R32', 2: 'S16', 3: 'E8', 4: 'FF', 5: 'Championship', 6: 'Champion',
};

export function buildGameId(region, round, gameIndex) {
  return `${region}_R${round}_G${gameIndex + 1}`;
}

export function getRoundSlotYs(round, regionTop, regionH) {
  const count = 16 / Math.pow(2, round - 1);
  const spacing = regionH / count;
  return Array.from({ length: count }, (_, i) =>
    regionTop + spacing * i + spacing / 2
  );
}

export function buildBracketLayout(simulationData, pendingLocks) {
  if (!simulationData?.teams || !simulationData?.matchups) {
    return { slots: [], matchups: [] };
  }

  const teams = simulationData.teams;
  const apiMatchups = simulationData.matchups;
  const locked = pendingLocks ?? {};

  const regionBands = {
    East:    { side: 'left',  top: 0,                height: SVG_HEIGHT / 2 },
    South:   { side: 'left',  top: SVG_HEIGHT / 2, height: SVG_HEIGHT / 2 },
    West:    { side: 'right', top: 0,                height: SVG_HEIGHT / 2 },
    Midwest: { side: 'right', top: SVG_HEIGHT / 2, height: SVG_HEIGHT / 2 },
  };

  const slots = [];
  const matchups = [];

  // Track FF winners per region for championship game
  const ffWinners = {};

  for (const region of REGIONS) {
    const band = regionBands[region];
    const isLeft = band.side === 'left';

    const seedMap = {};
    for (const [name, t] of Object.entries(teams)) {
      if (t.region === region) seedMap[t.seed] = { name, ...t };
    }

    // roundSlots[r][i] = team occupying slot i in round r
    const roundSlots = {};
    roundSlots[1] = SEED_ORDER.map(seed => seedMap[seed]);

    for (let r = 2; r <= 5; r++) {
      const prevTeams = roundSlots[r - 1];
      roundSlots[r] = [];
      const gamesInPrev = prevTeams.length / 2;
      for (let gameIdx = 0; gameIdx < gamesInPrev; gameIdx++) {
        const gameId = buildGameId(region, r - 1, gameIdx);
        const lockedName = locked[gameId];
        if (lockedName) {
          const teamA = prevTeams[gameIdx * 2];
          const teamB = prevTeams[gameIdx * 2 + 1];
          const winner =
            teamA?.name === lockedName ? teamA :
            teamB?.name === lockedName ? teamB :
            { name: lockedName, seed: '?', advancement: {}, region };
          roundSlots[r].push(winner);
        } else {
          roundSlots[r].push(null);
        }
      }
    }

    // Record FF winner (round 5, slot 0) for championship
    ffWinners[region] = roundSlots[5]?.[0] ?? null;

    // Build slot and matchup objects for rounds 1-5
    for (let r = 1; r <= 5; r++) {
      const teamsInRound = roundSlots[r];
      if (!teamsInRound?.length) continue;

      const roundX = isLeft ? LEFT_ROUND_X[r] : RIGHT_ROUND_X[r];
      const slotYs = getRoundSlotYs(r, band.top, band.height);

      for (let i = 0; i < teamsInRound.length; i++) {
        const team = teamsInRound[i];
        const y = slotYs[i] - SLOT_H / 2;

        let prob = 0;
        if (r === 1 && team) {
          const gameId = buildGameId(region, 1, Math.floor(i / 2));
          const apiM = apiMatchups[gameId];
          if (apiM) prob = i % 2 === 0 ? apiM.win_prob_a : apiM.win_prob_b;
        }

        const topCandidates = (!team && r >= 2)
          ? getCandidates(teams, r, i, roundSlots[r - 1])
          : [];

        const sourceGameId = r >= 2 ? buildGameId(region, r - 1, i) : null;

        slots.push({
          id: `${region}_R${r}_S${i}`,
          x: roundX,
          y,
          teamName: team?.name ?? null,
          seed: team?.seed ?? null,
          round: r,
          region,
          isLeft,
          prob,
          topCandidates,
          isTBD: !team,
          sourceGameId,
        });
      }

      for (let i = 0; i < teamsInRound.length; i += 2) {
        const slotA = slots.find(s => s.id === `${region}_R${r}_S${i}`);
        const slotB = slots.find(s => s.id === `${region}_R${r}_S${i + 1}`);
        const gameId = buildGameId(region, r, i / 2);

        matchups.push({
          gameId,
          round: r,
          region,
          teamA: teamsInRound[i]?.name ?? null,
          teamB: teamsInRound[i + 1]?.name ?? null,
          slotAId: slotA?.id,
          slotBId: slotB?.id,
          isLeft,
          apiMatchup: r === 1 ? apiMatchups[gameId] : null,
        });
      }
    }
  }

  // ── Championship game ──────────────────────────────────────────────────────
  // ── Final Four & Championship ─────────────────────────────────────────────
  //
  // Four FF team slots (one per region, showing who reached the FF):
  //   East FF winner:    x = LEFT_ROUND_X[5],  top half y
  //   South FF winner:   x = LEFT_ROUND_X[5],  bottom half y
  //   West FF winner:    x = RIGHT_ROUND_X[5], top half y
  //   Midwest FF winner: x = RIGHT_ROUND_X[5], bottom half y
  //
  // These are already built by the regional loop above (round 5 slots).
  //
  // Two semifinal game slots (who plays in the FF game):
  //   FF_G1: East vs West   → slot at CHAMP_LEFT_X,  CHAMP_Y
  //   FF_G2: South vs Midwest → slot at CHAMP_RIGHT_X, CHAMP_Y
  //
  // One championship slot at CHAMPION_X, CHAMPION_Y

  const semiFinals = [
    {
      gameId: 'FF_G1',
      regionA: 'East',    // left side top
      regionB: 'South',   // left side bottom
      slotX: CHAMP_LEFT_X,
    },
    {
      gameId: 'FF_G2',
      regionA: 'West',    // right side top
      regionB: 'Midwest', // right side bottom
      slotX: CHAMP_RIGHT_X,
    },
  ];

  const finalists = [];

  for (const sf of semiFinals) {
    const teamA = ffWinners[sf.regionA]; // left side winner
    const teamB = ffWinners[sf.regionB]; // right side winner
    const lockedName = locked[sf.gameId];

    let winner = null;
    if (lockedName) {
      winner = teamA?.name === lockedName ? teamA
        : teamB?.name === lockedName ? teamB
        : { name: lockedName, seed: '?', advancement: {} };
    }

    finalists.push(winner);

    const candidates = [teamA, teamB]
      .filter(Boolean)
      .map(t => ({
        name: t.name,
        seed: t.seed,
        prob: teams[t.name]?.advancement?.Championship ?? 0,
      }))
      .sort((a, b) => b.prob - a.prob);

    slots.push({
      id: `FF_Slot_${sf.gameId}`,
      x: sf.slotX,
      y: CHAMP_Y - SLOT_H / 2,
      teamName: winner?.name ?? null,
      seed: winner?.seed ?? null,
      round: 6,
      region: 'Final Four',
      isLeft: sf.slotX === CHAMP_LEFT_X,
      prob: winner ? (teams[winner.name]?.advancement?.Championship ?? 0) : 0,
      topCandidates: candidates,
      isTBD: !winner,
      sourceGameId: sf.gameId,
      isFinalistSlot: true,
    });

    matchups.push({
      gameId: sf.gameId,
      round: 5,
      region: 'Final Four',
      teamA: teamA?.name ?? null,
      teamB: teamB?.name ?? null,
      slotAId: null,
      slotBId: null,
      isLeft: sf.slotX === CHAMP_LEFT_X,
      isFinalFour: true,
    });
  }

  // Championship slot
  const champLockedName = locked['Championship'];
  const champTeamA = finalists[0];
  const champTeamB = finalists[1];

  let champion = null;
  if (champLockedName) {
    champion = champTeamA?.name === champLockedName ? champTeamA
      : champTeamB?.name === champLockedName ? champTeamB
      : { name: champLockedName, seed: '?', advancement: {} };
  }

  const champCandidates = [champTeamA, champTeamB]
    .filter(Boolean)
    .map(t => ({
      name: t.name,
      seed: t.seed,
      prob: teams[t.name]?.advancement?.Champion ?? 0,
    }))
    .sort((a, b) => b.prob - a.prob);

  slots.push({
    id: 'Championship_S0',
    x: CHAMPION_X,
    y: CHAMPION_Y - SLOT_H / 2,
    teamName: champion?.name ?? null,
    seed: champion?.seed ?? null,
    round: 7,
    region: 'Championship',
    isLeft: true,
    prob: champion ? (teams[champion.name]?.advancement?.Champion ?? 0) : 0,
    topCandidates: champCandidates,
    isTBD: !champion,
    sourceGameId: 'Championship',
    isChampionSlot: true,
  });

  matchups.push({
    gameId: 'Championship',
    round: 6,
    region: 'Championship',
    teamA: champTeamA?.name ?? null,
    teamB: champTeamB?.name ?? null,
    slotAId: 'FF_Slot_FF_G1',
    slotBId: 'FF_Slot_FF_G2',
    isLeft: true,
    isChampionship: true,
  });

  return { slots, matchups };
}

function getCandidates(teams, round, slotIndex, prevRoundTeams) {
  const feedA = prevRoundTeams?.[slotIndex * 2];
  const feedB = prevRoundTeams?.[slotIndex * 2 + 1];
  const advKey = ROUND_ADV_KEYS[round - 1] ?? 'R32';

  return [feedA, feedB]
    .filter(Boolean)
    .map(t => ({
      name: t.name,
      seed: t.seed,
      prob: teams[t.name]?.advancement?.[advKey] ?? 0,
    }))
    .sort((a, b) => b.prob - a.prob);
}
