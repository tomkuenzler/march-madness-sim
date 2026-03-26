<script>
  import { simulationData, actualResults } from '$lib/stores/simulation.js';
  import { onMount } from 'svelte';
  import axios from 'axios';

  const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

  let roundOddsData = $state(null);

  onMount(async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/odds/rounds`);
      if (res.data.available) roundOddsData = res.data;
    } catch { /* silent fail */ }
  });

  const ROUND_DISPLAY = {
    R32: 'R32', S16: 'S16', E8: 'E8', FF: 'FF',
    Championship: 'Final', Champion: '🏆 Win',
  };

  const americanToImplied = (american) => {
    const n = parseInt(american);
    if (isNaN(n)) return null;
    if (n < 0) return Math.abs(n) / (Math.abs(n) + 100);
    return 100 / (n + 100);
  };

  const toAmerican = (p) => {
    if (p <= 0) return '+99999';
    if (p >= 1) return '-99999';
    if (p >= 0.5) return String(Math.round(-p / (1 - p) * 100));
    return `+${Math.round((1 - p) / p * 100)}`;
  };

  // Active round for matchups
  let activeFanDuelRound = $derived(
    Object.keys($actualResults).some(k => k.includes('_R4_')) ? 'Champion' :
    Object.keys($actualResults).some(k => k.includes('_R3_')) ? 'FF' :
    Object.keys($actualResults).some(k => k.includes('_R2_')) ? 'E8' :
    Object.keys($actualResults).some(k => k.includes('_R1_')) ? 'S16' : 'R32'
  );

  const ODDS_ROUND_TO_RESULT_KEY = {
    S16: '_R1_', E8: '_R2_', FF: '_R3_',
    Championship: '_R4_',
  };
  const ODDS_ROUND_TO_NEXT_GAME = {
    S16: 2, E8: 3, FF: 4, Championship: 5,
  };

  // Best matchup bets — KenPom head-to-head vs FanDuel
  let bestMatchupBets = $derived(() => {
    if (!roundOddsData) return [];
    const odds = roundOddsData.teams ?? {};
    const roundKey = activeFanDuelRound;
    const layoutMatchups = $simulationData?.matchups ?? {};
    const resultKeyFilter = ODDS_ROUND_TO_RESULT_KEY[roundKey];
    const nextGameRound = ODDS_ROUND_TO_NEXT_GAME[roundKey];
    if (!resultKeyFilter || !nextGameRound) return [];

    const winnersByRegion = {};
    for (const [gameId, winner] of Object.entries($actualResults)) {
      if (!gameId.includes(resultKeyFilter)) continue;
      const match = gameId.match(/^([A-Za-z]+)_R\d+_G(\d+)$/);
      if (!match) continue;
      const region = match[1];
      const gameNum = parseInt(match[2]);
      if (!winnersByRegion[region]) winnersByRegion[region] = {};
      winnersByRegion[region][gameNum] = winner;
    }

    const bets = [];
    for (const region of ['East', 'West', 'South', 'Midwest']) {
      const regionWinners = winnersByRegion[region] ?? {};
      const gameNums = Object.keys(regionWinners).map(Number).sort((a, b) => a - b);
      for (let i = 0; i < gameNums.length; i += 2) {
        const teamA = regionWinners[gameNums[i]];
        const teamB = regionWinners[gameNums[i + 1]];
        if (!teamA || !teamB) continue;
        const nextGameId = `${region}_R${nextGameRound}_G${Math.floor(i / 2) + 1}`;
        const nextMatchup = layoutMatchups[nextGameId];
        if (!nextMatchup) continue;

        for (const [team, isA] of [[teamA, true], [teamB, false]]) {
          const teamOdds = odds[team]?.rounds?.[roundKey];
          if (!teamOdds) continue;
          const modelProb = isA
            ? (nextMatchup.team_a === teamA ? nextMatchup.win_prob_a : nextMatchup.win_prob_b)
            : (nextMatchup.team_a === teamA ? nextMatchup.win_prob_b : nextMatchup.win_prob_a);
          const fdImplied = americanToImplied(teamOdds.american);
          if (fdImplied === null) continue;
          const edge = modelProb - fdImplied;
          if (edge <= 0) continue;
          bets.push({
            team,
            round: roundKey,
            roundLabel: ROUND_DISPLAY[roundKey] ?? roundKey,
            odds: teamOdds.odds,
            modelOdds: toAmerican(modelProb),
            modelPct: modelProb,
            fdPct: fdImplied,
            edge,
            edgePct: `+${(edge * 100).toFixed(1)}%`,
            isValue: edge >= 0.03,
            type: 'matchup',
          });
        }
      }
    }
    return bets.sort((a, b) => b.edge - a.edge).slice(0, 5);
  });

  // Best futures bets — simulation advancement vs FanDuel futures
  let bestFutureBets = $derived(() => {
    if (!roundOddsData) return [];
    const simTeams = $simulationData?.teams ?? {};
    const odds = roundOddsData.teams ?? {};
    const roundOrder = ['R32', 'S16', 'E8', 'FF', 'Championship', 'Champion'];
    const activeRoundKey = activeFanDuelRound;
    const activeIdx = roundOrder.indexOf(activeRoundKey);
    const futureRounds = roundOrder.slice(activeIdx);

    const bets = [];
    for (const [teamName, teamOdds] of Object.entries(odds)) {
      const simTeam = simTeams[teamName];
      if (!simTeam) continue;
      for (const round of futureRounds) {
        const rd = teamOdds.rounds?.[round];
        if (!rd || rd.edge === undefined) continue;
        if (rd.edge <= 0) continue;
        bets.push({
          team: teamName,
          round,
          roundLabel: ROUND_DISPLAY[round] ?? round,
          odds: rd.odds,
          modelOdds: rd.model_odds,
          modelPct: rd.model_pct,
          fdPct: rd.no_vig_implied,
          edge: rd.edge,
          edgePct: rd.edge_pct,
          isValue: rd.is_value,
          type: 'future',
        });
      }
    }
    return bets.sort((a, b) => b.edge - a.edge).slice(0, 5);
  });

  function edgeColor(edge) {
    if (edge >= 0.08) return '#4ade80';
    if (edge >= 0.05) return '#86efac';
    if (edge >= 0.03) return '#facc15';
    return '#94a3b8';
  }
</script>

{#if roundOddsData}
  <div class="best-bets">
    <div class="best-bets-header">
      <span class="best-bets-title">💰 Best Bets</span>
      <span class="best-bets-sub">Top edges vs FanDuel · 3%+ threshold · Not financial advice</span>
    </div>

    <div class="best-bets-cols">

      <!-- Current Matchup Bets -->
      <div class="bets-section">
        <div class="bets-section-title">Current Matchups</div>
        {@const matchupBets = bestMatchupBets()}
        {#if matchupBets.length === 0}
          <div class="no-bets">No value bets found in current matchups</div>
        {:else}
          {#each matchupBets as bet}
            <div class="bet-row" class:is-value={bet.isValue}>
              <div class="bet-left">
                <span class="bet-team">{bet.team}</span>
                <span class="bet-round">{bet.roundLabel}</span>
              </div>
              <div class="bet-right">
                <span class="bet-odds">{bet.odds}</span>
                <span class="bet-model">Model: {bet.modelOdds}</span>
                <span class="bet-edge" style="color:{edgeColor(bet.edge)}">{bet.edgePct}</span>
              </div>
            </div>
          {/each}
        {/if}
      </div>

      <!-- Futures Bets -->
      <div class="bets-section">
        <div class="bets-section-title">Futures</div>
        {@const futureBets = bestFutureBets()}
        {#if futureBets.length === 0}
          <div class="no-bets">No value bets found in futures</div>
        {:else}
          {#each futureBets as bet}
            <div class="bet-row" class:is-value={bet.isValue}>
              <div class="bet-left">
                <span class="bet-team">{bet.team}</span>
                <span class="bet-round">{bet.roundLabel}</span>
              </div>
              <div class="bet-right">
                <span class="bet-odds">{bet.odds}</span>
                <span class="bet-model">Model: {bet.modelOdds}</span>
                <span class="bet-edge" style="color:{edgeColor(bet.edge)}">{bet.edgePct}</span>
              </div>
            </div>
          {/each}
        {/if}
      </div>

    </div>
  </div>
{/if}

<style>
  .best-bets {
    background: #161925;
    border: 1px solid #2a3148;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 1.5rem;
  }

  .best-bets-header {
    display: flex;
    align-items: baseline;
    gap: 1rem;
    padding: 0.75rem 1.25rem;
    background: #1e2538;
    border-bottom: 1px solid #2a3148;
  }

  .best-bets-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: #f0f4ff;
  }

  .best-bets-sub {
    font-size: 0.72rem;
    color: #475569;
  }

  .best-bets-cols {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
  }

  .bets-section {
    padding: 0.75rem 1.25rem;
  }

  .bets-section:first-child {
    border-right: 1px solid #2a3148;
  }

  .bets-section-title {
    font-size: 0.72rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.6rem;
  }

  .bet-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.45rem 0.6rem;
    border-radius: 6px;
    margin-bottom: 0.35rem;
    background: #1e2538;
    border: 1px solid #2a3148;
    transition: border-color 0.15s;
  }

  .bet-row.is-value {
    border-color: #4ade8040;
    background: #0f1f10;
  }

  .bet-left {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }

  .bet-team {
    font-size: 0.85rem;
    font-weight: 600;
    color: #e2e8f0;
  }

  .bet-round {
    font-size: 0.68rem;
    color: #475569;
  }

  .bet-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .bet-odds {
    font-size: 0.82rem;
    font-weight: 700;
    color: #f0f4ff;
    min-width: 48px;
    text-align: right;
  }

  .bet-model {
    font-size: 0.72rem;
    color: #93c5fd;
    min-width: 72px;
    text-align: right;
  }

  .bet-edge {
    font-size: 0.82rem;
    font-weight: 700;
    min-width: 48px;
    text-align: right;
  }

  .no-bets {
    font-size: 0.78rem;
    color: #334155;
    padding: 0.5rem 0;
    text-align: center;
  }
</style>
