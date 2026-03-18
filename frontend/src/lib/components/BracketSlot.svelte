<script>
  import { pendingLocks } from '$lib/stores/simulation.js';
  import { SLOT_W, SLOT_H } from '$lib/bracketLayout.js';

  let { slot, onclick } = $props();

  let isLocked = $derived(
    slot.teamName !== null &&
    Object.values($pendingLocks).includes(slot.teamName)
  );

  // Only show win probability on R1 slots (the known first-round matchups)
  let showProb = $derived(slot.round === 1 && slot.prob > 0);

  function truncate(name, max = 15) {
    if (!name) return '';
    return name.length > max ? name.slice(0, max - 1) + '…' : name;
  }

  function winProbColor(prob) {
    if (prob >= 0.75) return '#4ade80';
    if (prob >= 0.55) return '#facc15';
    if (prob >= 0.45) return '#fb923c';
    return '#f87171';
  }
</script>

<g
  class="slot-group"
  role="button"
  tabindex="0"
  onclick={onclick}
  onkeydown={(e) => e.key === 'Enter' && onclick(e)}
  style="cursor: pointer"
>
  <!-- Slot background -->
  <rect
    x={slot.x}
    y={slot.y}
    width={SLOT_W}
    height={SLOT_H}
    rx="3"
    fill={isLocked ? '#1f1a0e' : slot.isTBD ? '#12151e' : '#1e2538'}
    stroke={isLocked ? '#f59e0b' : slot.isTBD ? '#1e2538' : '#2a3148'}
    stroke-width="1"
  />

  {#if slot.isTBD}
    <!-- TBD slot: show top 2 candidates -->
    {#if slot.topCandidates?.length > 0}
      {#each slot.topCandidates.slice(0, 2) as candidate, i}
        <text
          x={slot.x + 5}
          y={slot.y + 10 + i * 11}
          font-size="8.5"
          fill="#3a4560"
        >#{candidate.seed} {truncate(candidate.name, 13)}</text>
      {/each}
    {:else}
      <text x={slot.x + 5} y={slot.y + 18} font-size="9" fill="#2a3148">TBD</text>
    {/if}
  {:else}
    <!-- Seed badge background -->
    <rect
      x={slot.x + 2}
      y={slot.y + 4}
      width={18}
      height={20}
      rx="2"
      fill="#161925"
    />
    <!-- Seed number -->
    <text
      x={slot.x + 11}
      y={slot.y + 18}
      font-size="9"
      text-anchor="middle"
      fill="#64748b"
      font-weight="600"
    >{slot.seed}</text>

    <!-- Team name -->
    <text
      x={slot.x + 24}
      y={slot.y + 18}
      font-size="10"
      fill={isLocked ? '#fbbf24' : '#e2e8f0'}
      font-weight={isLocked ? '700' : '400'}
    >{truncate(slot.teamName, showProb ? 12 : 16)}</text>

    <!-- Win probability (R1 only) -->
    {#if showProb}
      <text
        x={slot.x + SLOT_W - 4}
        y={slot.y + 18}
        font-size="9"
        text-anchor="end"
        fill={winProbColor(slot.prob)}
        font-weight="600"
      >{(slot.prob * 100).toFixed(0)}%</text>
    {/if}

    <!-- Lock indicator -->
    {#if isLocked}
      <circle cx={slot.x + SLOT_W - 6} cy={slot.y + 8} r="4" fill="#78350f" />
      <text x={slot.x + SLOT_W - 6} y={slot.y + 11} font-size="6" text-anchor="middle" fill="#fde68a">🔒</text>
    {/if}
  {/if}
</g>

<style>
  .slot-group:hover rect:first-of-type {
    stroke: #3b82f6;
  }
</style>
