<script>
  import { simulationData } from '$lib/stores/simulation.js';
  import BracketSVG from './BracketSVG.svelte';
  import BestBets from './BestBets.svelte';
  import OddsTable from './OddsTable.svelte';

  function getAdv(teamName, round) {
    return $simulationData?.teams?.[teamName]?.advancement?.[round] ?? 0;
  }

  function getRegionFavorite(region) {
    if (!$simulationData?.teams) return null;
    return Object.entries($simulationData.teams)
      .filter(([, t]) => t.region === region)
      .sort((a, b) => b[1].advancement.Champion - a[1].advancement.Champion)[0];
  }

  const ffPairs = [['East', 'West'], ['South', 'Midwest']];
</script>

<div class="bracket-container">

  <!-- Championship odds bar -->
  <div class="odds-bar">
    <span class="odds-label">Championship Odds</span>
    <div class="odds-teams">
      {#each Object.entries($simulationData?.teams ?? {})
        .sort((a, b) => b[1].advancement.Champion - a[1].advancement.Champion)
        .slice(0, 8) as [name, stats]}
        <div class="odds-chip">
          <span class="odds-seed">#{stats.seed}</span>
          <span class="odds-name">{name}</span>
          <span class="odds-pct">{(stats.advancement.Champion * 100).toFixed(1)}%</span>
        </div>
      {/each}
    </div>
  </div>

  <!-- Traditional SVG bracket -->
  <BracketSVG />

  <!-- Tabbed odds/leverage/betting table -->
  <BestBets />
  <OddsTable />

  <!-- Insights section -->
  <div class="insights-grid">

    <!-- Championship bar chart -->
    <div class="insight-card">
      <h3 class="card-title">🏆 Championship Favorites</h3>
      {#each Object.entries($simulationData?.teams ?? {})
        .sort((a, b) => b[1].advancement.Champion - a[1].advancement.Champion)
        .slice(0, 8) as [name, stats]}
        <div class="bar-row">
          <span class="bar-seed">#{stats.seed}</span>
          <span class="bar-name">{name}</span>
          <div class="bar-track">
            <div
              class="bar-fill"
              style="width: {Math.min(stats.advancement.Champion * 400, 100)}%"
            ></div>
          </div>
          <span class="bar-pct">{(stats.advancement.Champion * 100).toFixed(1)}%</span>
        </div>
      {/each}
    </div>

    <!-- Most likely Final Four -->
    <div class="insight-card">
      <h3 class="card-title">🎯 Most Likely Final Four</h3>
      <div class="ff-grid">
        {#each ['East', 'West', 'South', 'Midwest'] as region}
          {@const fav = getRegionFavorite(region)}
          {#if fav}
            <div class="ff-entry">
              <span class="ff-region">{region}</span>
              <span class="ff-seed">#{fav[1].seed}</span>
              <span class="ff-name">{fav[0]}</span>
              <span class="ff-prob">{(fav[1].advancement.FF * 100).toFixed(1)}%</span>
            </div>
          {/if}
        {/each}
      </div>
    </div>

    <!-- Upset alerts -->
    <div class="insight-card">
      <h3 class="card-title">⚡ R1 Upset Alerts</h3>
      {#each Object.entries($simulationData?.matchups ?? {})
        .filter(([, m]) => m.upset_alert)
        .sort((a, b) => Math.abs(b[1].win_prob_a - 0.5) - Math.abs(a[1].win_prob_a - 0.5)) as [id, m]}
        <div class="upset-row">
          <span class="upset-seeds">#{m.seed_a} vs #{m.seed_b}</span>
          <span class="upset-teams">{m.team_a} vs {m.team_b}</span>
          <span class="upset-prob">{(Math.max(m.win_prob_a, m.win_prob_b) * 100).toFixed(0)}% / {(Math.min(m.win_prob_a, m.win_prob_b) * 100).toFixed(0)}%</span>
        </div>
      {/each}
      {#if Object.values($simulationData?.matchups ?? {}).filter(m => m.upset_alert).length === 0}
        <p class="no-upsets">No significant upset alerts this year.</p>
      {/if}
    </div>

  </div>

</div>

<style>
  .bracket-container {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    padding: 1rem;
  }

  /* Odds bar */
  .odds-bar {
    display: flex;
    align-items: center;
    gap: 1rem;
    background: #161925;
    border: 1px solid #2a3148;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    overflow-x: auto;
  }

  .odds-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #64748b;
    white-space: nowrap;
  }

  .odds-teams { display: flex; gap: 0.5rem; flex-wrap: wrap; }

  .odds-chip {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    background: #1e2535;
    border: 1px solid #2a3148;
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
  }

  .odds-seed { color: #64748b; }
  .odds-name { color: #e2e8f0; font-weight: 500; }
  .odds-pct { color: #fbbf24; font-weight: 700; }

  /* Section */
  .section {
    background: #161925;
    border: 1px solid #2a3148;
    border-radius: 10px;
    padding: 1.25rem;
  }

  .section-title {
    font-size: 0.85rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 1rem;
  }

  /* Odds table */
  .table-wrap { overflow-x: auto; }

  .odds-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }

  .odds-table th {
    text-align: left;
    padding: 0.5rem 0.75rem;
    color: #64748b;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 1px solid #2a3148;
    white-space: nowrap;
  }

  .odds-table td {
    padding: 0.4rem 0.75rem;
    border-bottom: 1px solid #1e2538;
    color: #94a3b8;
  }

  .odds-table tr:hover td { background: #1e2535; }
  .team-name-cell { font-weight: 600; color: #f0f4ff; white-space: nowrap; }
  .num-cell { color: #64748b; }
  .region-cell { color: #64748b; font-size: 0.75rem; }
  .champ-cell { color: #fbbf24; font-weight: 700; }

  /* Insights grid */
  .insights-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
  }

  .insight-card {
    background: #161925;
    border: 1px solid #2a3148;
    border-radius: 10px;
    padding: 1.25rem;
  }

  .card-title {
    font-size: 0.82rem;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 1rem;
  }

  /* Bar chart */
  .bar-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    font-size: 0.8rem;
  }

  .bar-seed { color: #64748b; min-width: 24px; }
  .bar-name { color: #e2e8f0; min-width: 100px; font-weight: 500; }

  .bar-track {
    flex: 1;
    height: 6px;
    background: #2a3148;
    border-radius: 3px;
    overflow: hidden;
  }

  .bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #3b82f6, #fbbf24);
    border-radius: 3px;
    transition: width 0.4s ease;
  }

  .bar-pct { color: #fbbf24; font-weight: 700; min-width: 38px; text-align: right; font-size: 0.78rem; }

  /* Final Four */
  .ff-grid { display: flex; flex-direction: column; gap: 0.6rem; }

  .ff-entry {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.82rem;
    background: #1e2535;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
  }

  .ff-region { color: #64748b; min-width: 56px; font-size: 0.72rem; text-transform: uppercase; }
  .ff-seed { color: #64748b; min-width: 24px; }
  .ff-name { flex: 1; color: #e2e8f0; font-weight: 600; }
  .ff-prob { color: #a78bfa; font-weight: 700; }

  /* Upset rows */
  .upset-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.78rem;
    padding: 0.4rem 0;
    border-bottom: 1px solid #1e2538;
  }

  .upset-seeds { color: #64748b; min-width: 70px; }
  .upset-teams { flex: 1; color: #e2e8f0; }
  .upset-prob { color: #f87171; font-weight: 600; white-space: nowrap; }
  .no-upsets { color: #475569; font-size: 0.82rem; text-align: center; padding: 1rem 0; }
</style>
