<script>
  import { simulationData, pendingLocks, removeAdvancement, gameScores } from '$lib/stores/simulation.js';
  import TeamCard from './TeamCard.svelte';

  let { game, onclose } = $props();

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) onclose();
  }

  // Is this game's source locked? Which team?
  let lockedTeam = $derived(
    game.source_game_id ? $pendingLocks[game.source_game_id] : null
  );

  function handleRemoveLock() {
    if (game.source_game_id) {
      removeAdvancement(game.source_game_id);
      onclose();
    }
  }

  const ROUND_NAMES = {
    1: 'Round of 64',
    2: 'Round of 32',
    3: 'Sweet 16',
    4: 'Elite 8',
    5: 'Final Four',
    6: 'Championship',
  };
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="backdrop" onclick={handleBackdropClick}>
  <div class="modal">

    <!-- Header -->
    <div class="modal-header">
      <div>
        <span class="round-label">{ROUND_NAMES[game.round] ?? `Round ${game.round}`} · {game.region}</span>
        <h2 class="modal-title">{game.team_a} vs {game.team_b}</h2>
        {#if game.completed_winner}
          <div class="completed-banner">
            ✓ {game.completed_winner} won
            {#if $gameScores[game.game_id]}
              {$gameScores[game.game_id]}
            {/if}
          </div>
        {/if}
      </div>
      <button class="close-btn" onclick={() => onclose()}>✕</button>
    </div>

    <!-- Win probability bar -->
    <div class="prob-section">
      <div class="prob-labels">
        <span class="prob-team">{game.team_a}</span>
        <span class="prob-values">
          {(game.win_prob_a * 100).toFixed(1)}% — {(game.win_prob_b * 100).toFixed(1)}%
        </span>
        <span class="prob-team right">{game.team_b}</span>
      </div>
      <div class="prob-bar">
        <div class="prob-fill-a" style="width: {game.win_prob_a * 100}%"></div>
      </div>
      <div class="spread-label">
        {#if game.point_diff > 0}
          {game.team_a} favored by {Math.abs(game.point_diff).toFixed(1)} pts
        {:else if game.point_diff < 0}
          {game.team_b} favored by {Math.abs(game.point_diff).toFixed(1)} pts
        {:else}
          Even matchup
        {/if}
      </div>
    </div>

    {#if game.upset_alert}
      <div class="upset-banner">
        ⚡ Upset Alert — closer than the seeds suggest
      </div>
    {/if}

    <!-- Team stat cards -->
    <div class="teams-grid">
      <TeamCard teamName={game.team_a} seed={game.seed_a} winProb={game.win_prob_a} />
      <TeamCard teamName={game.team_b} seed={game.seed_b} winProb={game.win_prob_b} />
    </div>

    <!-- Advancement odds comparison -->
    {#if $simulationData?.teams?.[game.team_a] && $simulationData?.teams?.[game.team_b]}
      {@const teamA = $simulationData.teams[game.team_a]}
      {@const teamB = $simulationData.teams[game.team_b]}
      <div class="adv-section">
        <div class="adv-title">Advancement Odds (from last simulation)</div>
        <table class="adv-table">
          <thead>
            <tr>
              <th>Round</th>
              <th>{game.team_a}</th>
              <th>{game.team_b}</th>
            </tr>
          </thead>
          <tbody>
            {#each [['R32','R32'],['S16','Sweet 16'],['E8','Elite 8'],['FF','Final Four'],['Champion','Champion']] as [key, label]}
              <tr>
                <td class="round-name">{label}</td>
                <td style="color: {(teamA.advancement[key] ?? 0) > (teamB.advancement[key] ?? 0) ? '#4ade80' : '#94a3b8'}">
                  {((teamA.advancement[key] ?? 0) * 100).toFixed(1)}%
                </td>
                <td style="color: {(teamB.advancement[key] ?? 0) > (teamA.advancement[key] ?? 0) ? '#4ade80' : '#94a3b8'}">
                  {((teamB.advancement[key] ?? 0) * 100).toFixed(1)}%
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    {#if lockedTeam}
      <div class="lock-status">
        <div class="lock-status-text">
          🔒 <strong>{lockedTeam}</strong> is manually locked into this slot
        </div>
        <button class="remove-lock-btn" onclick={handleRemoveLock}>
          Remove Lock
        </button>
      </div>
    {/if}

    <div class="modal-hint">
      💡 To advance a team, click their slot directly in the bracket
    </div>

  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.75);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 200;
    padding: 1rem;
    backdrop-filter: blur(2px);
  }

  .modal {
    background: #141824;
    border: 1px solid #2a3148;
    border-radius: 12px;
    width: 100%;
    max-width: 600px;
    max-height: 90vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    padding: 1.5rem;
  }

  .modal-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .round-label {
    font-size: 0.72rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    display: block;
    margin-bottom: 0.25rem;
  }

  .modal-title { font-size: 1.15rem; font-weight: 700; color: #f0f4ff; }

  .close-btn {
    background: #2a3148;
    border: 1px solid #3a4560;
    color: #e2e8f0;
    font-size: 1rem;
    cursor: pointer;
    padding: 0.35rem 0.65rem;
    border-radius: 6px;
    line-height: 1;
    transition: background 0.15s;
    flex-shrink: 0;
  }

  .close-btn:hover { background: #3a4560; }

  .prob-section { background: #1e2538; border-radius: 8px; padding: 1rem; }

  .prob-labels {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.6rem;
    gap: 0.5rem;
  }

  .prob-team { font-size: 0.82rem; font-weight: 600; color: #cbd5e1; flex: 1; }
  .prob-team.right { text-align: right; }
  .prob-values { font-size: 0.82rem; color: #94a3b8; white-space: nowrap; text-align: center; }

  .prob-bar { height: 8px; background: #ef4444; border-radius: 4px; overflow: hidden; margin-bottom: 0.5rem; }
  .prob-fill-a { height: 100%; background: #3b82f6; border-radius: 4px; transition: width 0.3s ease; }

  .spread-label { font-size: 0.75rem; color: #64748b; text-align: center; }

  .upset-banner {
    background: #450a0a;
    border: 1px solid #991b1b;
    color: #fca5a5;
    padding: 0.6rem 1rem;
    border-radius: 6px;
    font-size: 0.8rem;
  }

  .teams-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }

  /* Advancement table */
  .adv-section { background: #1e2538; border-radius: 8px; padding: 1rem; }

  .adv-title {
    font-size: 0.72rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.75rem;
  }

  .adv-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }

  .adv-table th {
    text-align: left;
    padding: 0.35rem 0.5rem;
    color: #64748b;
    font-size: 0.72rem;
    font-weight: 600;
    border-bottom: 1px solid #2a3148;
  }

  .adv-table td { padding: 0.35rem 0.5rem; border-bottom: 1px solid #1e2538; color: #94a3b8; }
  .round-name { color: #64748b; font-size: 0.75rem; }

  .modal-hint {
    font-size: 0.75rem;
    color: #334155;
    text-align: center;
    padding: 0.25rem;
  }

  .lock-status {
    background: #1f1a0e;
    border: 1px solid #78350f;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .lock-status-text {
    font-size: 0.82rem;
    color: #fbbf24;
  }

  .remove-lock-btn {
    padding: 0.4rem 0.85rem;
    background: #2d1a00;
    border: 1px solid #f59e0b;
    color: #fbbf24;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s;
    flex-shrink: 0;
  }

  .remove-lock-btn:hover { background: #3d2400; }

  .completed-banner {
    background: #0f2010;
    border: 1px solid #4ade80;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: #4ade80;
    text-align: center;
  }
</style>
