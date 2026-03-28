<script>
  import { simulationData, actualResults } from '$lib/stores/simulation.js';
  import { onMount } from 'svelte';
  import axios from 'axios';

  const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

  let activeTab = $state('odds');
  let bettingSubTab = $state('matchups');
  let regionFilter = $state('All');

  let leverageData = $state(null);
  let leverageError = $state(null);
  let roundOddsData = $state(null);
  let roundOddsError = $state(null);
  let roundOddsLoading = $state(false);

  const REGIONS = ['All', 'East', 'West', 'South', 'Midwest'];

  const LEV_ROUNDS = ['R32', 'S16', 'E8', 'FF', 'Championship', 'Champion'];
  const LEV_LABELS = {
    R32: 'R32', S16: 'S16', E8: 'E8',
    FF: 'FF', Championship: 'Final', Champion: '🏆 Win'
  };

  const ROUND_DISPLAY_NAMES = {
    S16: 'Sweet 16', E8: 'Elite 8', FF: 'Final Four',
    Championship: 'Championship Game', Champion: 'Tournament Winner',
  };

  onMount(async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/leverage`);
      if (res.data.available) leverageData = res.data;
      else leverageError = res.data.message;
    } catch { leverageError = 'Failed to load leverage data'; }
    await loadRoundOdds();
  });

  async function loadRoundOdds() {
    roundOddsLoading = true;
    roundOddsError = null;
    try {
      const res = await axios.get(`${API_BASE}/api/odds/rounds`);
      if (res.data.available) roundOddsData = res.data;
      else roundOddsError = res.data.message ?? 'Round odds not available';
    } catch { roundOddsError = 'Failed to load round odds'; }
    finally { roundOddsLoading = false; }
  }

  // activeFanDuelRound: returns the CSV column for the round currently being played
  // Logic: R2 results exist → teams are playing S16 → they're trying to reach E8 → use E8 column
  let activeFanDuelRound = $derived(
    Object.keys($actualResults).some(k => k.includes('_R4_')) ? 'Champion' :
    Object.keys($actualResults).some(k => k.includes('_R3_')) ? 'FF' :
    Object.keys($actualResults).some(k => k.includes('_R2_')) ? 'E8' :
    Object.keys($actualResults).some(k => k.includes('_R1_')) ? 'S16' : 'R32'
  );

  // Map: the odds column → which results round the participants came from
  // E8 odds → teams won their _R2_ games → look for _R2_ in actualResults
  const ODDS_ROUND_TO_RESULT_KEY = {
    R32: '_R1_', S16: '_R1_', E8: '_R2_',
    FF: '_R3_', Championship: '_R4_',
  };

  // Map: the odds column → which game round number the next games are
  const ODDS_ROUND_TO_NEXT_GAME = {
    S16: 2, E8: 3, FF: 4, Championship: 5,
  };

  // Build current round matchup pairs from actualResults
  let currentMatchups = $derived(() => {
    if (!roundOddsData) return [];
    const odds = roundOddsData.teams ?? {};
    const roundKey = activeFanDuelRound;
    const layoutMatchups = $simulationData?.matchups ?? {};
    const simTeams = $simulationData?.teams ?? {};

    const resultKeyFilter = ODDS_ROUND_TO_RESULT_KEY[roundKey];
    const nextGameRound = ODDS_ROUND_TO_NEXT_GAME[roundKey];
    if (!resultKeyFilter || !nextGameRound) return [];

    // Collect winners from the previous round grouped by region and game number
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

    const pairs = [];

    for (const region of ['East', 'West', 'South', 'Midwest']) {
      if (regionFilter !== 'All' && region !== regionFilter) continue;
      const regionWinners = winnersByRegion[region] ?? {};
      const gameNums = Object.keys(regionWinners).map(Number).sort((a, b) => a - b);

      // Pair consecutive game winners: G1 vs G2, G3 vs G4, etc.
      for (let i = 0; i < gameNums.length; i += 2) {
        const teamA = regionWinners[gameNums[i]];
        const teamB = regionWinners[gameNums[i + 1]];
        if (!teamA || !teamB) continue;

        const oddsA = odds[teamA]?.rounds?.[roundKey];
        const oddsB = odds[teamB]?.rounds?.[roundKey];

        // Get model head-to-head probability from simulation matchups
        const nextGameId = `${region}_R${nextGameRound}_G${Math.floor(i / 2) + 1}`;
        const nextMatchup = layoutMatchups[nextGameId];

        let modelProbA = 0.5, modelProbB = 0.5;
        if (nextMatchup) {
          modelProbA = nextMatchup.team_a === teamA
            ? nextMatchup.win_prob_a
            : nextMatchup.win_prob_b;
          modelProbB = 1 - modelProbA;
        }

        const toAmerican = (p) => {
          if (p <= 0) return '+99999';
          if (p >= 1) return '-99999';
          if (p >= 0.5) return String(Math.round(-p / (1 - p) * 100));
          return `+${Math.round((1 - p) / p * 100)}`;
        };

        // Compute edge vs no-vig implied
        const americanToImplied = (american) => {
          const n = parseInt(american);
          if (n < 0) return Math.abs(n) / (Math.abs(n) + 100);
          return 100 / (n + 100);
        };

        // Convert FanDuel odds to raw implied (no vig removal)
        const fdImpliedA = oddsA ? americanToImplied(oddsA.american) : null;
        const fdImpliedB = oddsB ? americanToImplied(oddsB.american) : null;

        // Edge = model implied - fanduel implied (straight comparison, no vig)
        const edgeAVal = fdImpliedA !== null ? modelProbA - fdImpliedA : null;
        const edgeBVal = fdImpliedB !== null ? modelProbB - fdImpliedB : null;

        pairs.push({
          gameId: nextGameId,
          region,
          round: roundKey,
          teamA, teamB,
          seedA: simTeams[teamA]?.seed,
          seedB: simTeams[teamB]?.seed,
          fdOddsA: oddsA?.odds ?? '—',
          fdOddsB: oddsB?.odds ?? '—',
          modelOddsA: toAmerican(modelProbA),
          modelOddsB: toAmerican(modelProbB),
          edgeAVal,
          edgeBVal,
          edgeA: edgeAVal !== null ? `${edgeAVal > 0 ? '+' : ''}${(edgeAVal * 100).toFixed(1)}%` : '—',
          edgeB: edgeBVal !== null ? `${edgeBVal > 0 ? '+' : ''}${(edgeBVal * 100).toFixed(1)}%` : '—',
          isValueA: edgeAVal !== null && edgeAVal >= 0.03,
          isValueB: edgeBVal !== null && edgeBVal >= 0.03,
        });
      }
    }

    return pairs;
  });

  // All teams sorted by championship odds
  let allTeams = $derived(
    Object.entries($simulationData?.teams ?? {})
      .map(([name, t]) => ({ name, ...t }))
      .filter(t => regionFilter === 'All' || t.region === regionFilter)
      .sort((a, b) => b.advancement.Champion - a.advancement.Champion)
  );

  // Futures: only teams with odds in roundOddsData
  let aliveTeams = $derived(
    allTeams.filter(t => {
      // Team is alive if they have any non-zero advancement odds
      // for rounds that haven't been played yet
      const adv = t.advancement ?? {};
      const activeRoundKey = activeFanDuelRound;
      // Check rounds from current active round onwards
      const roundOrder = ['R32', 'S16', 'E8', 'FF', 'Championship', 'Champion'];
      const activeIdx = roundOrder.indexOf(activeRoundKey);
      return roundOrder.slice(activeIdx).some(r => (adv[r] ?? 0) > 0.001);
    })
  );

  function leverageColor(val) {
    if (val == null) return '#475569';
    if (val >= 0.05) return '#4ade80';
    if (val >= 0.02) return '#86efac';
    if (val >= -0.02) return '#94a3b8';
    if (val >= -0.05) return '#fca5a5';
    return '#ef4444';
  }

  function leverageLabel(val) {
    if (val == null) return '—';
    return `${val > 0 ? '+' : ''}${(val * 100).toFixed(1)}%`;
  }

  function edgeColor(edge) {
    if (edge == null) return '#475569';
    if (edge >= 0.05) return '#4ade80';
    if (edge >= 0.03) return '#86efac';
    if (edge >= 0) return '#94a3b8';
    if (edge >= -0.05) return '#fca5a5';
    return '#ef4444';
  }

  function advColor(prob, hi, lo) {
    if (prob >= hi) return '#4ade80';
    if (prob >= lo) return '#facc15';
    return '#f87171';
  }
</script>

<div class="odds-table-container">

  <!-- Tab bar + region filter -->
  <div class="table-controls">
    <div class="tabs">
      <button class="tab" class:active={activeTab === 'odds'} onclick={() => activeTab = 'odds'}>
        Full Tournament Odds
      </button>
      <button class="tab" class:active={activeTab === 'leverage'} onclick={() => activeTab = 'leverage'}>
        Leverage Scores
      </button>
      <button class="tab" class:active={activeTab === 'betting'} onclick={() => activeTab = 'betting'}>
        Betting Edge
      </button>
    </div>
    <div class="controls-right">
      <select class="region-select" bind:value={regionFilter}>
        {#each REGIONS as r}
          <option value={r}>{r}</option>
        {/each}
      </select>
    </div>
  </div>

  <!-- ── Full Tournament Odds ── -->
  {#if activeTab === 'odds'}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Team</th><th>Seed</th><th>Region</th>
            <th>R32</th><th>S16</th><th>E8</th><th>FF</th><th>Final</th><th>🏆 Win</th>
          </tr>
        </thead>
        <tbody>
          {#each allTeams as team}
            <tr>
              <td class="team-name">{team.name}</td>
              <td class="center">#{team.seed}</td>
              <td class="region-cell">{team.region}</td>
              <td style="color:{advColor(team.advancement.R32,0.6,0.4)}">{(team.advancement.R32*100).toFixed(0)}%</td>
              <td style="color:{advColor(team.advancement.S16,0.4,0.2)}">{(team.advancement.S16*100).toFixed(0)}%</td>
              <td style="color:{advColor(team.advancement.E8,0.25,0.1)}">{(team.advancement.E8*100).toFixed(0)}%</td>
              <td style="color:#a78bfa">{(team.advancement.FF*100).toFixed(0)}%</td>
              <td style="color:#93c5fd">{(team.advancement.Championship*100).toFixed(0)}%</td>
              <td class="champ-cell">{(team.advancement.Champion*100).toFixed(1)}%</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  <!-- ── Leverage Scores ── -->
  {#if activeTab === 'leverage'}
    {#if leverageError}
      <div class="info-banner">ℹ {leverageError}</div>
    {:else if !leverageData}
      <div class="info-banner">Loading leverage data...</div>
    {:else}
      <div class="leverage-meta">
        Sources: {leverageData.sources_loaded?.join(', ') ?? 'none'} ·
        Leverage = Model% − Consensus Pick% · Hover for details
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Team</th><th>Seed</th><th>Region</th>
              {#each LEV_ROUNDS as r}<th>{LEV_LABELS[r]}</th>{/each}
            </tr>
          </thead>
          <tbody>
            {#each allTeams as team}
              {@const lev = leverageData.teams?.[team.name]?.leverage}
              <tr>
                <td class="team-name">{team.name}</td>
                <td class="center">#{team.seed}</td>
                <td class="region-cell">{team.region}</td>
                {#each LEV_ROUNDS as r}
                  {@const entry = lev?.[r]}
                  <td
                    style="color:{leverageColor(entry?.leverage)}"
                    title={entry ? `Model: ${(entry.model*100).toFixed(1)}%  |  Consensus: ${entry.consensus != null ? (entry.consensus*100).toFixed(1)+'%' : 'N/A'}  |  Leverage: ${leverageLabel(entry.leverage)}` : 'No data'}
                  >
                    {leverageLabel(entry?.leverage)}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="legend">
        <span style="color:#4ade80">■</span> +5%+ underowned &nbsp;
        <span style="color:#86efac">■</span> +2–5% &nbsp;
        <span style="color:#94a3b8">■</span> roughly fair &nbsp;
        <span style="color:#fca5a5">■</span> −2–5% overowned &nbsp;
        <span style="color:#ef4444">■</span> −5%+ avoid
      </div>
    {/if}
  {/if}

  <!-- ── Betting Edge ── -->
  {#if activeTab === 'betting'}
    <div class="sub-tabs">
      <button class="sub-tab" class:active={bettingSubTab === 'matchups'} onclick={() => bettingSubTab = 'matchups'}>
        Current Matchups
      </button>
      <button class="sub-tab" class:active={bettingSubTab === 'futures'} onclick={() => bettingSubTab = 'futures'}>
        Futures
      </button>
    </div>

    {#if roundOddsError}
      <div class="info-banner">ℹ {roundOddsError}</div>
    {:else if roundOddsLoading}
      <div class="info-banner">Loading odds...</div>
    {:else if !roundOddsData}
      <div class="info-banner">No odds data available.</div>

    {:else if bettingSubTab === 'matchups'}
      {@const matchups = currentMatchups()}
      <span class="odds-note">Model odds use KenPom head-to-head formula (independent of bracket path)</span>
      {#if matchups.length === 0}
        <div class="info-banner">No matchup data available for the current round.</div>
      {:else}
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Region</th>
                <th>Team</th>
                <th>Seed</th>
                <th>FanDuel</th>
                <th>Model</th>
                <th>Edge</th>
                <th class="vs-th">vs</th>
                <th>Team</th>
                <th>Seed</th>
                <th>FanDuel</th>
                <th>Model</th>
                <th>Edge</th>
              </tr>
            </thead>
            <tbody>
              {#each matchups as m}
                <tr class:has-value={m.isValueA || m.isValueB}>
                  <td class="region-cell">{m.region}</td>
                  <td class="team-name">
                    {#if m.isValueA}<span class="value-badge">★</span>{/if}
                    {m.teamA}
                  </td>
                  <td class="center">#{m.seedA}</td>
                  <td class="odds-cell" class:value-odds={m.isValueA}>{m.fdOddsA}</td>
                  <td class="model-odds-cell">{m.modelOddsA}</td>
                  <td style="color:{edgeColor(m.edgeAVal)}" class:bold={m.isValueA}>{m.edgeA}</td>
                  <td class="vs-cell">vs</td>
                  <td class="team-name">
                    {#if m.isValueB}<span class="value-badge">★</span>{/if}
                    {m.teamB}
                  </td>
                  <td class="center">#{m.seedB}</td>
                  <td class="odds-cell" class:value-odds={m.isValueB}>{m.fdOddsB}</td>
                  <td class="model-odds-cell">{m.modelOddsB}</td>
                  <td style="color:{edgeColor(m.edgeBVal)}" class:bold={m.isValueB}>{m.edgeB}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <div class="legend">
            <span style="color:#4ade80">★</span> Value bet (3%+ edge) &nbsp;·&nbsp;
            <span style="color:#475569">Note: Model % in Futures tab uses simulation data and may differ slightly</span>
        </div>
      {/if}

    {:else}
      <!-- Futures sub-tab -->
      {@const ROUNDS = ['R32', 'S16', 'E8', 'FF', 'Championship', 'Champion']}
      {@const ROUND_LABELS = { R32: 'R32', S16: 'S16', E8: 'E8', FF: 'FF', Championship: 'Final', Champion: '🏆 Win' }}
      <div class="betting-meta-bar">
        <span>📊 FanDuel · Tournament Advancement Futures</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Team</th>
              <th>Seed</th>
              <th>Region</th>
              {#each ROUNDS as r}
                <th colspan="3" class="round-group-header">{ROUND_LABELS[r]}</th>
              {/each}
            </tr>
            <tr class="subheader">
              <th></th><th></th><th></th>
              {#each ROUNDS as _}
                <th class="sub">FanDuel</th>
                <th class="sub">Model</th>
                <th class="sub">Edge</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each aliveTeams as team}
              {@const betTeam = roundOddsData.teams?.[team.name]}
              <tr>
                <td class="team-name">{team.name}</td>
                <td class="center">#{team.seed}</td>
                <td class="region-cell">{team.region}</td>
                {#each ROUNDS as r}
                  {@const rd = betTeam?.rounds?.[r]}
                  {#if rd}
                    <td class="odds-cell" class:value-cell={rd.is_value}>{rd.odds}</td>
                    <td class="model-odds-cell">{rd.model_odds}</td>
                    <td
                      style="color:{edgeColor(rd.edge)}"
                      class:bold={rd.is_value}
                      title={`FD Implied: ${(rd.fd_implied * 100).toFixed(1)}% | Model: ${(rd.model_pct * 100).toFixed(1)}% | Edge: ${rd.edge_pct}`}
                    >{rd.edge_pct}</td>
                  {:else}
                    <td class="na">—</td><td class="na">—</td><td class="na">—</td>
                  {/if}
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="legend">
        <span style="color:#4ade80">■</span> Value (3%+ edge) &nbsp;
        <span style="color:#94a3b8">■</span> Fair &nbsp;
        <span style="color:#ef4444">■</span> Avoid
      </div>
    {/if}
  {/if}

</div>

<style>
  .odds-table-container {
    background: #161925;
    border: 1px solid #2a3148;
    border-radius: 10px;
    overflow: hidden;
  }

  .table-controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 1rem;
    background: #1e2538;
    border-bottom: 1px solid #2a3148;
    gap: 1rem;
  }

  .tabs { display: flex; }

  .tab {
    padding: 0.75rem 1.25rem;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: #64748b;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
    white-space: nowrap;
  }
  .tab:hover { color: #cbd5e1; }
  .tab.active { color: #f0f4ff; border-bottom-color: #3b82f6; }

  .region-select {
    background: #141824;
    border: 1px solid #2a3148;
    color: #cbd5e1;
    border-radius: 6px;
    padding: 0.35rem 0.6rem;
    font-size: 0.8rem;
    cursor: pointer;
  }

  .sub-tabs {
    display: flex;
    background: #141824;
    border-bottom: 1px solid #2a3148;
    padding: 0 1rem;
  }

  .sub-tab {
    padding: 0.5rem 1rem;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: #475569;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }
  .sub-tab:hover { color: #94a3b8; }
  .sub-tab.active { color: #93c5fd; border-bottom-color: #3b82f6; }

  .betting-meta-bar {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    padding: 0.6rem 1rem;
    border-bottom: 1px solid #1e2538;
    font-size: 0.78rem;
    color: #64748b;
  }
  .odds-note { font-size: 0.7rem; color: #334155; }

  .table-wrap { overflow-x: auto; padding: 0.5rem 0; }

  table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }

  th {
    text-align: left;
    padding: 0.5rem 0.6rem;
    color: #64748b;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid #2a3148;
    white-space: nowrap;
  }

  th.round-group-header {
    text-align: center;
    border-left: 1px solid #2a3148;
    color: #94a3b8;
    font-size: 0.72rem;
  }

  th.vs-th { text-align: center; width: 30px; }

  tr.subheader th {
    color: #334155;
    font-size: 0.65rem;
    padding: 0.25rem 0.6rem;
    border-bottom: 1px solid #1e2538;
  }

  th.sub { text-align: center; }

  td {
    padding: 0.4rem 0.6rem;
    border-bottom: 1px solid #1e2538;
    color: #94a3b8;
    white-space: nowrap;
  }

  tr:hover td { background: #1e2538; }
  tr:last-child td { border-bottom: none; }

  .team-name { font-weight: 600; color: #f0f4ff; }
  .center { text-align: center; }
  .region-cell { color: #64748b; font-size: 0.75rem; }
  .champ-cell { color: #fbbf24; font-weight: 700; }
  .odds-cell { color: #e2e8f0; font-weight: 600; text-align: center; }
  .value-odds { color: #4ade80 !important; }
  .model-odds-cell { color: #93c5fd; font-weight: 600; text-align: center; }
  .value-cell { color: #4ade80 !important; }
  .bold { font-weight: 700; }
  .na { color: #2a3148; text-align: center; }
  .vs-cell { color: #334155; text-align: center; font-size: 0.7rem; }

  .has-value td:first-child { border-left: 2px solid #4ade80; }
  .value-badge { color: #4ade80; margin-right: 0.25rem; font-size: 0.7rem; }

  .leverage-meta {
    padding: 0.6rem 1rem;
    font-size: 0.75rem;
    color: #475569;
    border-bottom: 1px solid #1e2538;
  }

  .legend {
    padding: 0.6rem 1rem;
    font-size: 0.72rem;
    color: #475569;
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    border-top: 1px solid #1e2538;
  }

  .info-banner {
    padding: 1.5rem 1rem;
    text-align: center;
    color: #475569;
    font-size: 0.82rem;
  }
</style>
