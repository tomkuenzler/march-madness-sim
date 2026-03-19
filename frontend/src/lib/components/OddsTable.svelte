<script>
  import { simulationData } from '$lib/stores/simulation.js';
  import { onMount } from 'svelte';
  import axios from 'axios';

  const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

  let activeTab = $state('odds');
  let regionFilter = $state('All');

  let leverageData = $state(null);
  let leverageError = $state(null);
  let roundOddsData = $state(null);
  let roundOddsError = $state(null);
  let roundOddsLoading = $state(false);

  const REGIONS = ['All', 'East', 'West', 'South', 'Midwest'];
  const ROUNDS = ['R32', 'S16', 'E8', 'FF', 'Championship'];
  const ROUND_LABELS = {
    R32: 'R32', S16: 'S16', E8: 'E8', FF: 'FF', Championship: 'Final'
  };

  const LEV_ROUNDS = ['R32', 'S16', 'E8', 'FF', 'Championship', 'Champion'];
  const LEV_LABELS = {
    R32: 'R32', S16: 'S16', E8: 'E8',
    FF: 'FF', Championship: 'Final', Champion: '🏆 Win'
  };

  onMount(async () => {
    // Load leverage
    try {
      const res = await axios.get(`${API_BASE}/api/leverage`);
      if (res.data.available) leverageData = res.data;
      else leverageError = res.data.message;
    } catch { leverageError = 'Failed to load leverage data'; }

    // Load round odds
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

  // Sorted filtered teams
  let allTeams = $derived(
    Object.entries($simulationData?.teams ?? {})
      .map(([name, t]) => ({ name, ...t }))
      .filter(t => regionFilter === 'All' || t.region === regionFilter)
      .sort((a, b) => b.advancement.Champion - a.advancement.Champion)
  );

  function leverageColor(val) {
    if (val == null) return '#475569';
    if (val >= 0.05)  return '#4ade80';
    if (val >= 0.02)  return '#86efac';
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
    if (edge >= 0.05)  return '#4ade80';
    if (edge >= 0.03)  return '#86efac';
    if (edge >= 0)     return '#94a3b8';
    if (edge >= -0.05) return '#fca5a5';
    return '#ef4444';
  }

  function advColor(prob, hi, lo) {
    if (prob >= hi)  return '#4ade80';
    if (prob >= lo)  return '#facc15';
    return '#f87171';
  }

  // Check if a team has any value bets across any round
  function hasValueBet(teamName) {
    const team = roundOddsData?.teams?.[teamName];
    if (!team) return false;
    return Object.values(team.rounds).some(r => r?.is_value);
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
                    title={entry
                      ? `Model: ${(entry.model*100).toFixed(1)}%  |  Consensus: ${entry.consensus != null ? (entry.consensus*100).toFixed(1)+'%' : 'N/A'}  |  Leverage: ${leverageLabel(entry.leverage)}`
                      : 'No data'}
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
    {#if roundOddsError}
      <div class="info-banner">ℹ {roundOddsError}</div>
    {:else if roundOddsLoading}
      <div class="info-banner">Loading odds...</div>
    {:else if !roundOddsData}
      <div class="info-banner">No odds data available.</div>
    {:else}
      <div class="betting-meta-bar">
        <span>📊 {roundOddsData.bookmaker} · Round-by-Round Advancement Odds</span>
        <span class="odds-note">{roundOddsData.note}</span>
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
            {#each allTeams as team}
              {@const betTeam = roundOddsData.teams?.[team.name]}
              <tr class:has-value={hasValueBet(team.name)}>
                <td class="team-name">
                  {#if hasValueBet(team.name)}<span class="value-badge">★</span>{/if}
                  {team.name}
                </td>
                <td class="center">#{team.seed}</td>
                <td class="region-cell">{team.region}</td>
                {#each ROUNDS as r}
                  {@const rd = betTeam?.rounds?.[r]}
                  {#if rd}
                    <td class="odds-cell" class:value-cell={rd.is_value}>{rd.odds}</td>
                    <td class="model-odds-cell">{rd.model_odds}</td>
                    <td style="color:{edgeColor(rd.edge)}" class:bold={rd.is_value}>{rd.edge_pct}</td>
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
        <span style="color:#ef4444">■</span> Avoid &nbsp;·&nbsp;
        Edge = Model% − No-Vig Implied%
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
    text-align: left;
  }

  tr:hover td { background: #1e2538; }
  tr:last-child td { border-bottom: none; }

  .team-name { font-weight: 600; color: #f0f4ff; }
  .center { text-align: center; }
  .region-cell { color: #64748b; font-size: 0.75rem; }
  .champ-cell { color: #fbbf24; font-weight: 700; }

  .odds-cell { color: #e2e8f0; font-weight: 600; text-align: center; }
  .model-odds-cell { color: #93c5fd; font-weight: 600; text-align: center; }
  .value-cell { color: #4ade80 !important; }
  .bold { font-weight: 700; }
  .na { color: #2a3148; text-align: center; }

  .has-value td:first-child { border-left: 2px solid #4ade80; }

  .value-badge { color: #4ade80; margin-right: 0.25rem; font-size: 0.7rem; }

  /* Leverage */
  .leverage-meta {
    padding: 0.6rem 1rem;
    font-size: 0.75rem;
    color: #475569;
    border-bottom: 1px solid #1e2538;
  }

  /* Betting meta bar */
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
