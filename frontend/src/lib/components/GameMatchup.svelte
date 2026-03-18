<script>
  import { lockedResults, simulationData } from '$lib/stores/simulation.js';

  let { game, onclick } = $props();

  let isLocked = $derived($lockedResults?.[game.game_id] !== undefined);
  let lockedWinner = $derived($lockedResults?.[game.game_id]);
  let upsetAlert = $derived(game.upset_alert);

  function getAdv(teamName, round) {
    return $simulationData?.teams?.[teamName]?.advancement?.[round] ?? 0;
  }

  function pctColor(prob) {
    if (prob >= 0.75) return '#22c55e';
    if (prob >= 0.55) return '#3b82f6';
    if (prob >= 0.45) return '#f59e0b';
    return '#ef4444';
  }

  function advColor(prob, threshold1, threshold2) {
    if (prob >= threshold1) return '#4ade80';
    if (prob >= threshold2) return '#facc15';
    return '#f87171';
  }
</script>

<button
  class="matchup-card"
  class:locked={isLocked}
  class:upset-alert={upsetAlert}
  onclick={onclick}
  title="Click for game details"
>
  {#if isLocked}
    <div class="lock-badge">🔒 Locked</div>
  {/if}
  {#if upsetAlert}
    <div class="upset-badge">⚡ Upset Alert</div>
  {/if}

  <!-- Team rows with inline advancement stats -->
  <div class="team-row" class:winner={lockedWinner === game.team_a}>
    <span class="seed">#{game.seed_a}</span>
    <span class="name">{game.team_a}</span>
    <span class="win-prob" style="color: {pctColor(game.win_prob_a)}">
      {(game.win_prob_a * 100).toFixed(1)}%
    </span>
  </div>
  <div class="adv-row">
    <span style="color: {advColor(getAdv(game.team_a,'R32'),0.6,0.4)}">R32: {(getAdv(game.team_a,'R32')*100).toFixed(0)}%</span>
    <span style="color: {advColor(getAdv(game.team_a,'S16'),0.4,0.2)}">S16: {(getAdv(game.team_a,'S16')*100).toFixed(0)}%</span>
    <span style="color: {advColor(getAdv(game.team_a,'E8'),0.25,0.1)}">E8: {(getAdv(game.team_a,'E8')*100).toFixed(0)}%</span>
    <span style="color: #a78bfa">FF: {(getAdv(game.team_a,'FF')*100).toFixed(0)}%</span>
    <span style="color: #fbbf24">🏆 {(getAdv(game.team_a,'Champion')*100).toFixed(1)}%</span>
  </div>

  <div class="divider"></div>

  <div class="team-row" class:winner={lockedWinner === game.team_b}>
    <span class="seed">#{game.seed_b}</span>
    <span class="name">{game.team_b}</span>
    <span class="win-prob" style="color: {pctColor(game.win_prob_b)}">
      {(game.win_prob_b * 100).toFixed(1)}%
    </span>
  </div>
  <div class="adv-row">
    <span style="color: {advColor(getAdv(game.team_b,'R32'),0.6,0.4)}">R32: {(getAdv(game.team_b,'R32')*100).toFixed(0)}%</span>
    <span style="color: {advColor(getAdv(game.team_b,'S16'),0.4,0.2)}">S16: {(getAdv(game.team_b,'S16')*100).toFixed(0)}%</span>
    <span style="color: {advColor(getAdv(game.team_b,'E8'),0.25,0.1)}">E8: {(getAdv(game.team_b,'E8')*100).toFixed(0)}%</span>
    <span style="color: #a78bfa">FF: {(getAdv(game.team_b,'FF')*100).toFixed(0)}%</span>
    <span style="color: #fbbf24">🏆 {(getAdv(game.team_b,'Champion')*100).toFixed(1)}%</span>
  </div>

  <div class="point-diff">{Math.abs(game.point_diff).toFixed(1)} pt spread</div>
</button>

<style>
  .matchup-card {
    width: 100%;
    background: #1e2538;
    border: 1px solid #2a3148;
    border-radius: 6px;
    padding: 0.5rem 0.6rem;
    cursor: pointer;
    text-align: left;
    transition: border-color 0.15s, background 0.15s;
  }

  .matchup-card:hover {
    border-color: #3b82f6;
    background: #212840;
  }

  .matchup-card.locked {
    border-color: #f59e0b;
    background: #1f1a0e;
  }

  .matchup-card.upset-alert {
    border-color: #ef4444;
  }

  .lock-badge, .upset-badge {
    font-size: 0.6rem;
    font-weight: 600;
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    margin-bottom: 0.3rem;
    display: inline-block;
  }

  .lock-badge { background: #78350f; color: #fde68a; }
  .upset-badge { background: #450a0a; color: #fca5a5; }

  .team-row {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.15rem 0;
  }

  .team-row.winner .name { color: #fbbf24; font-weight: 700; }

  .seed { font-size: 0.65rem; color: #475569; min-width: 18px; }

  .name {
    flex: 1;
    font-size: 0.75rem;
    color: #cbd5e1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .win-prob { font-size: 0.75rem; font-weight: 700; min-width: 38px; text-align: right; }

  .adv-row {
    display: flex;
    gap: 0.5rem;
    padding: 0.15rem 0 0.2rem 1.5rem;
    flex-wrap: wrap;
  }

  .adv-row span {
    font-size: 0.65rem;
    font-weight: 600;
  }

  .divider { height: 1px; background: #2a3148; margin: 0.25rem 0; }

  .point-diff {
    font-size: 0.62rem;
    color: #475569;
    text-align: center;
    margin-top: 0.25rem;
  }
</style>