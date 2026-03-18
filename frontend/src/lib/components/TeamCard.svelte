<script>
  import { simulationData } from '$lib/stores/simulation.js';

  let { teamName, seed, winProb } = $props();

  let team = $derived($simulationData?.teams?.[teamName]);

  function netRtgColor(val) {
    if (val >= 25) return '#22c55e';
    if (val >= 15) return '#3b82f6';
    if (val >= 5) return '#f59e0b';
    return '#ef4444';
  }

  function probColor(prob) {
    if (prob >= 0.75) return '#22c55e';
    if (prob >= 0.55) return '#3b82f6';
    if (prob >= 0.45) return '#f59e0b';
    return '#ef4444';
  }
</script>

{#if team}
  <div class="team-card">
    <div class="card-header">
      <span class="seed-badge">#{seed}</span>
      <span class="team-name">{teamName}</span>
      <span class="region">{team.region}</span>
    </div>

    <div class="stats-grid">
      <div class="stat">
        <span class="stat-label">NetRTG</span>
        <span class="stat-value" style="color: {netRtgColor(team.adj_em)}">
          {team.adj_em > 0 ? '+' : ''}{team.adj_em.toFixed(1)}
        </span>
      </div>
      <div class="stat">
        <span class="stat-label">Off Eff</span>
        <span class="stat-value">{team.adj_o.toFixed(1)}</span>
      </div>
      <div class="stat">
        <span class="stat-label">Def Eff</span>
        <span class="stat-value">{team.adj_d.toFixed(1)}</span>
      </div>
      <div class="stat">
        <span class="stat-label">Tempo</span>
        <span class="stat-value">{team.adj_t.toFixed(1)}</span>
      </div>
    </div>

    <div class="divider"></div>

    <div class="advancement-grid">
      <div class="adv-stat">
        <span class="adv-label">Win Prob</span>
        <span class="adv-value" style="color: {probColor(winProb)}">
          {(winProb * 100).toFixed(1)}%
        </span>
      </div>
      <div class="adv-stat">
        <span class="adv-label">To S16</span>
        <span class="adv-value">{(team.advancement.S16 * 100).toFixed(1)}%</span>
      </div>
      <div class="adv-stat">
        <span class="adv-label">To FF</span>
        <span class="adv-value">{(team.advancement.FF * 100).toFixed(1)}%</span>
      </div>
      <div class="adv-stat champion">
        <span class="adv-label">🏆 Win</span>
        <span class="adv-value gold">{(team.advancement.Champion * 100).toFixed(1)}%</span>
      </div>
    </div>
  </div>
{:else}
  <div class="team-card empty">
    <p>No data for {teamName}</p>
  </div>
{/if}

<style>
  .team-card {
    background: #1e2538;
    border: 1px solid #2a3148;
    border-radius: 8px;
    padding: 0.875rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .team-card.empty {
    color: #475569;
    font-size: 0.8rem;
    align-items: center;
    justify-content: center;
    min-height: 120px;
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .seed-badge {
    background: #2a3148;
    color: #64748b;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
  }

  .team-name {
    flex: 1;
    font-weight: 700;
    font-size: 0.9rem;
    color: #f0f4ff;
  }

  .region {
    font-size: 0.68rem;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.4rem;
  }

  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    background: #141824;
    border-radius: 5px;
    padding: 0.35rem 0.25rem;
  }

  .stat-label {
    font-size: 0.6rem;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.2rem;
  }

  .stat-value {
    font-size: 0.8rem;
    font-weight: 700;
    color: #e2e8f0;
  }

  .divider {
    height: 1px;
    background: #2a3148;
  }

  .advancement-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.4rem;
  }

  .adv-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    background: #141824;
    border-radius: 5px;
    padding: 0.35rem 0.25rem;
  }

  .adv-label {
    font-size: 0.6rem;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.2rem;
  }

  .adv-value {
    font-size: 0.8rem;
    font-weight: 700;
    color: #3b82f6;
  }

  .adv-value.gold {
    color: #fbbf24;
  }
</style>
