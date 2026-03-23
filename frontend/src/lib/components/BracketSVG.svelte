<script>
  import { simulationData, pendingLocks, actualResults, fetchMatchup, 
           advanceTeam, removeAdvancement, setGameResult, clearSingleResult } 
    from '$lib/stores/simulation.js';
  import { buildBracketLayout, buildGameId, SVG_WIDTH, SVG_HEIGHT, SLOT_W, SLOT_H,
           LEFT_ROUND_X, RIGHT_ROUND_X, CHAMP_LEFT_X, CHAMP_RIGHT_X, CHAMP_Y,
           CHAMPION_X, CHAMPION_Y, ROUND_ADV_KEYS,
           LEFT_SPINE_X, RIGHT_SPINE_X } from '$lib/bracketLayout.js';
  import BracketSlot from './BracketSlot.svelte';
  import GameModal from './GameModal.svelte';

  let modalOpen = $state(false);
  let modalGame = $state(null);
  let advanceModalOpen = $state(false);
  let advanceContext = $state(null);
  let resultModalOpen = $state(false);
  let resultContext = $state(null);
  // Determine active round from results
  let activeRound = $derived(
    Object.keys($actualResults).some(k => k.includes('_R4_')) ? 5 :
    Object.keys($actualResults).some(k => k.includes('_R3_')) ? 4 :
    Object.keys($actualResults).some(k => k.includes('_R2_')) ? 3 :
    Object.keys($actualResults).some(k => k.includes('_R1_')) ? 2 : 1
  );
  let eliminatedTeams = $derived(
    layout.slots.reduce((eliminated, slot) => {
      if (!slot.teamName || slot.isTBD || !slot.sourceGameId) return eliminated;
      const matchup = layout.matchups.find(m => m.gameId === slot.sourceGameId);
      if (!matchup || !matchup.teamA || !matchup.teamB) return eliminated;
      const loser = matchup.teamA === slot.teamName ? matchup.teamB : matchup.teamA;
      if (loser) eliminated[loser] = slot.round - 1; // loser's slot is one round back
      return eliminated;
    }, {})
  );
  $effect(() => {
    console.log('activeRound:', activeRound);
    const s16slots = layout.slots.filter(s => s.round === 3 && !s.isTBD);
    console.log('S16 non-TBD slots:', s16slots.length, s16slots.map(s => s.teamName));
    // Log ALL unique round values in the layout
    const rounds = [...new Set(layout.slots.map(s => s.round))].sort();
    console.log('All slot rounds in layout:', rounds);
    console.log('Sample S16 slot:', layout.slots.find(s => !s.isTBD && s.teamName === 'Duke' && s.round !== 1));
    console.log('Duke S16 full object:', JSON.stringify(layout.slots.find(s => s.teamName === 'Duke' && s.round === 3)));
  }); 

  let mergedLocks = $derived({ ...$actualResults, ...$pendingLocks });
  let layout = $derived(buildBracketLayout($simulationData, mergedLocks));

  const ROUND_DISPLAY = {
    1: 'Round of 64', 2: 'Round of 32', 3: 'Sweet 16',
    4: 'Elite 8', 5: 'Final Four', 6: 'Championship', 7: 'Championship',
  };

  const ROUND_LABELS = ['R64', 'R32', 'S16', 'E8', 'FF'];

  // Region spine labels: centered vertically in each region band, rotated 90°
  // Positioned in the narrow gap between E8 and FF columns
  const regionLabels = [
    { label: 'EAST',    x: LEFT_SPINE_X,  y: SVG_HEIGHT * 0.25 },
    { label: 'SOUTH',   x: LEFT_SPINE_X,  y: SVG_HEIGHT * 0.75 },
    { label: 'WEST',    x: RIGHT_SPINE_X, y: SVG_HEIGHT * 0.25 },
    { label: 'MIDWEST', x: RIGHT_SPINE_X, y: SVG_HEIGHT * 0.75 },
  ];

  function buildLines(slots, matchupList) {
    const lines = [];
    const slotMap = Object.fromEntries(slots.map(s => [s.id, s]));

    for (const m of matchupList) {
      const slotA = slotMap[m.slotAId];
      const slotB = slotMap[m.slotBId];
      if (!slotA || !slotB) continue;

      const yCenterA = slotA.y + SLOT_H / 2;
      const yCenterB = slotB.y + SLOT_H / 2;
      const yMid = (yCenterA + yCenterB) / 2;

      if (m.isLeft) {
        const xRight = slotA.x + SLOT_W;
        // Round 5 (FF) connects down to the finalist slot, not horizontally
        const nextX = m.round < 4 ? LEFT_ROUND_X[m.round + 1]
          : m.round === 4 ? LEFT_ROUND_X[5]
          : CHAMP_LEFT_X; // FF → left finalist
        lines.push({ x1: xRight,      y1: yCenterA, x2: xRight + 16, y2: yCenterA });
        lines.push({ x1: xRight,      y1: yCenterB, x2: xRight + 16, y2: yCenterB });
        lines.push({ x1: xRight + 16, y1: yCenterA, x2: xRight + 16, y2: yCenterB });
        lines.push({ x1: xRight + 16, y1: yMid,     x2: nextX,       y2: yMid     });
      } else {
        const xLeft = slotA.x;
        const nextX = m.round < 4 ? RIGHT_ROUND_X[m.round + 1] + SLOT_W
          : m.round === 4 ? RIGHT_ROUND_X[5] + SLOT_W
          : CHAMP_RIGHT_X + SLOT_W; // FF → right finalist
        lines.push({ x1: xLeft,      y1: yCenterA, x2: xLeft - 16,  y2: yCenterA });
        lines.push({ x1: xLeft,      y1: yCenterB, x2: xLeft - 16,  y2: yCenterB });
        lines.push({ x1: xLeft - 16, y1: yCenterA, x2: xLeft - 16,  y2: yCenterB });
        lines.push({ x1: xLeft - 16, y1: yMid,     x2: nextX,       y2: yMid     });
      }
    }
    return lines;
  }

  let connectorLines = $derived(buildLines(layout.slots, layout.matchups));
  // Championship geometry comes from bracketLayout constants

  async function handleSlotClick(slot) {

    // Round 5 regional slots (FF participants)
    if (slot.round === 5 && slot.teamName && !slot.isFinalistSlot) {
      const ffMatchup = layout.matchups.find(m =>
        m.isFinalFour && (m.teamA === slot.teamName || m.teamB === slot.teamName)
      );
      if (ffMatchup && ffMatchup.teamA && ffMatchup.teamB) {
        // Check for actual result
        if ($actualResults[ffMatchup.gameId]) {
          resultContext = { gameId: ffMatchup.gameId, teamA: ffMatchup.teamA, teamB: ffMatchup.teamB, winner: $actualResults[ffMatchup.gameId], round: 5, region: 'Final Four' };
          resultModalOpen = true;
          return;
        }
        const data = await fetchMatchup(ffMatchup.teamA, ffMatchup.teamB);
        if (!data) return;
        modalGame = {
          game_id: ffMatchup.gameId, round: 5, region: 'Final Four',
          team_a: ffMatchup.teamA, team_b: ffMatchup.teamB,
          seed_a: $simulationData?.teams?.[ffMatchup.teamA]?.seed,
          seed_b: $simulationData?.teams?.[ffMatchup.teamB]?.seed,
          win_prob_a: data.win_prob_a, win_prob_b: data.win_prob_b,
          point_diff: data.point_diff, upset_alert: data.upset_alert,
          source_game_id: slot.sourceGameId,
        };
        modalOpen = true;
        return;
      }
    }

    // FF finalist slot
    if (slot.isFinalistSlot) {
      const ffMatchup = layout.matchups.find(m => m.gameId === slot.sourceGameId);
      if (slot.isTBD && ffMatchup) {
        let candidates = slot.topCandidates ?? [];
        if (candidates.length === 2 && candidates[0]?.name && candidates[1]?.name) {
          const h2h = await fetchMatchup(candidates[0].name, candidates[1].name);
          if (h2h) {
            candidates = [
              { ...candidates[0], prob: h2h.win_prob_a, isH2H: true },
              { ...candidates[1], prob: h2h.win_prob_b, isH2H: true },
            ];
          }
        }
        advanceContext = { gameId: slot.sourceGameId, candidates, round: slot.round, region: slot.region, advRoundKey: 'Championship', targetRoundLabel: 'Championship', isH2H: candidates[0]?.isH2H ?? false };
        advanceModalOpen = true;
        return;
      }
      if (!slot.isTBD && ffMatchup?.teamA && ffMatchup?.teamB) {
        // Check for actual result
        if ($actualResults[ffMatchup.gameId]) {
          resultContext = { gameId: ffMatchup.gameId, teamA: ffMatchup.teamA, teamB: ffMatchup.teamB, winner: $actualResults[ffMatchup.gameId], round: 6, region: 'Final Four' };
          resultModalOpen = true;
          return;
        }
        const data = await fetchMatchup(ffMatchup.teamA, ffMatchup.teamB);
        if (!data) return;
        modalGame = {
          game_id: ffMatchup.gameId, round: 6, region: 'Final Four',
          team_a: ffMatchup.teamA, team_b: ffMatchup.teamB,
          seed_a: $simulationData?.teams?.[ffMatchup.teamA]?.seed,
          seed_b: $simulationData?.teams?.[ffMatchup.teamB]?.seed,
          win_prob_a: data.win_prob_a, win_prob_b: data.win_prob_b,
          point_diff: data.point_diff, upset_alert: data.upset_alert,
          source_game_id: slot.sourceGameId,
        };
        modalOpen = true;
      }
      return;
    }

    // Championship slot
    if (slot.isChampionSlot) {
      const champMatchup = layout.matchups.find(m => m.gameId === 'Championship');
      if (slot.isTBD && champMatchup) {
        let candidates = slot.topCandidates ?? [];
        if (candidates.length === 2 && candidates[0]?.name && candidates[1]?.name) {
          const h2h = await fetchMatchup(candidates[0].name, candidates[1].name);
          if (h2h) {
            candidates = [
              { ...candidates[0], prob: h2h.win_prob_a, isH2H: true },
              { ...candidates[1], prob: h2h.win_prob_b, isH2H: true },
            ];
          }
        }
        advanceContext = { gameId: 'Championship', candidates, round: slot.round, region: 'Championship', advRoundKey: 'Champion', targetRoundLabel: 'Champion', isH2H: candidates[0]?.isH2H ?? false };
        advanceModalOpen = true;
        return;
      }
      if (!slot.isTBD && champMatchup?.teamA && champMatchup?.teamB) {
        if ($actualResults['Championship']) {
          resultContext = { gameId: 'Championship', teamA: champMatchup.teamA, teamB: champMatchup.teamB, winner: $actualResults['Championship'], round: 6, region: 'Championship' };
          resultModalOpen = true;
          return;
        }
        const data = await fetchMatchup(champMatchup.teamA, champMatchup.teamB);
        if (!data) return;
        modalGame = {
          game_id: 'Championship', round: 6, region: 'Championship',
          team_a: champMatchup.teamA, team_b: champMatchup.teamB,
          seed_a: $simulationData?.teams?.[champMatchup.teamA]?.seed,
          seed_b: $simulationData?.teams?.[champMatchup.teamB]?.seed,
          win_prob_a: data.win_prob_a, win_prob_b: data.win_prob_b,
          point_diff: data.point_diff, upset_alert: data.upset_alert,
          source_game_id: 'Championship',
        };
        modalOpen = true;
      }
      return;
    }

    // Regular regional slots (rounds 1-4)
    const matchup = layout.matchups.find(m =>
      m.slotAId === slot.id || m.slotBId === slot.id
    );
    if (!matchup) return;

    // Check for actual result first
    if ($actualResults[matchup.gameId]) {
      resultContext = {
        gameId: matchup.gameId,
        teamA: matchup.teamA,
        teamB: matchup.teamB,
        winner: $actualResults[matchup.gameId],
        round: matchup.round,
        region: matchup.region,
      };
      resultModalOpen = true;
      return;
    }

    if (matchup.teamA && matchup.teamB) {
      const data = await fetchMatchup(matchup.teamA, matchup.teamB);
      if (!data) return;
      modalGame = {
        game_id: matchup.gameId, round: matchup.round, region: matchup.region,
        team_a: matchup.teamA, team_b: matchup.teamB,
        seed_a: $simulationData?.teams?.[matchup.teamA]?.seed,
        seed_b: $simulationData?.teams?.[matchup.teamB]?.seed,
        win_prob_a: data.win_prob_a, win_prob_b: data.win_prob_b,
        point_diff: data.point_diff, upset_alert: data.upset_alert,
        source_game_id: slot.sourceGameId ?? null,
      };
      modalOpen = true;
    } else {
      const gameId = slot.sourceGameId;
      if (!gameId) return;
      const advRoundKey = ROUND_ADV_KEYS[slot.round - 1] ?? 'R32';
      let candidates = slot.topCandidates ?? [];
      if (candidates.length === 2 && candidates[0]?.name && candidates[1]?.name) {
        const h2h = await fetchMatchup(candidates[0].name, candidates[1].name);
        if (h2h) {
          candidates = [
            { ...candidates[0], prob: h2h.win_prob_a, isH2H: true },
            { ...candidates[1], prob: h2h.win_prob_b, isH2H: true },
          ];
        }
      }
      advanceContext = { gameId, candidates, round: slot.round, region: slot.region, advRoundKey, targetRoundLabel: ROUND_DISPLAY[slot.round] ?? `Round ${slot.round}`, isH2H: candidates[0]?.isH2H ?? false };
      advanceModalOpen = true;
    }
  }

  function handleAdvance(teamName, gameId) {
    advanceTeam(gameId, teamName);
    advanceModalOpen = false;
    advanceContext = null;
  }

  function handleRemove(gameId) {
    removeAdvancement(gameId);
    advanceModalOpen = false;
    advanceContext = null;
  }

  function closeModal() { modalOpen = false; modalGame = null; }
  function closeAdvanceModal() { advanceModalOpen = false; advanceContext = null; }
</script>

<div class="bracket-svg-wrapper">
  <svg
    viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}"
    width="100%"
    preserveAspectRatio="xMidYMid meet"
    class="bracket-svg"
  >
    <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="#0f1117" />

    <!-- Quadrant dividers -->
    <line x1={SVG_WIDTH/2} y1={20} x2={SVG_WIDTH/2} y2={SVG_HEIGHT-20}
      stroke="#1e2538" stroke-width="1" stroke-dasharray="4,4" />
    <line x1={80} y1={SVG_HEIGHT/2} x2={SVG_WIDTH-80} y2={SVG_HEIGHT/2}
      stroke="#1e2538" stroke-width="1" stroke-dasharray="4,4" />

    <!-- Round column headers -->
    {#each ROUND_LABELS as label, i}
      <text x={LEFT_ROUND_X[i+1] + SLOT_W/2} y={14}
        font-size="8" text-anchor="middle" fill="#2a3148" letter-spacing="1.5">{label}</text>
      <text x={RIGHT_ROUND_X[i+1] + SLOT_W/2} y={14}
        font-size="8" text-anchor="middle" fill="#2a3148" letter-spacing="1.5">{label}</text>
    {/each}

    <!-- Region spine labels (rotated 90°) -->
    {#each regionLabels as rl}
      <text
        x={rl.x} y={rl.y}
        font-size="12" font-weight="800" fill="#1e2d40"
        text-anchor="middle" letter-spacing="3"
      >{rl.label}</text>
    {/each}

    <!-- Connector lines -->
    {#each connectorLines as line}
      <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2}
        stroke="#2a3148" stroke-width="1" />
    {/each}

    <!-- Team slots -->
    {#each layout.slots as slot}
      <BracketSlot {slot} {activeRound} {eliminatedTeams} onclick={() => handleSlotClick(slot)} />
    {/each}

    <!-- Finalist slots (side by side, fed by FF games) -->
    {#if layout.slots.length > 0}
      {@const finalistLeft  = layout.slots.find(s => s.id === 'FF_Slot_FF_G1')}
      {@const finalistRight = layout.slots.find(s => s.id === 'FF_Slot_FF_G2')}
      {@const champSlot     = layout.slots.find(s => s.id === 'Championship_S0')}

    <!-- Connector lines from FF slots down to finalist slots -->
    {#if finalistLeft}
      <line x1={CHAMP_LEFT_X + SLOT_W/2} y1={CHAMP_Y - SLOT_H/2 - 16}
            x2={CHAMP_LEFT_X + SLOT_W/2} y2={CHAMP_Y - SLOT_H/2}
            stroke="#2a3148" stroke-width="1" />
    {/if}
    {#if finalistRight}
      <line x1={CHAMP_RIGHT_X + SLOT_W/2} y1={CHAMP_Y - SLOT_H/2 - 16}
            x2={CHAMP_RIGHT_X + SLOT_W/2} y2={CHAMP_Y - SLOT_H/2}
            stroke="#2a3148" stroke-width="1" />
    {/if}

    <!-- Lines from finalist slots down to champion box -->
    {#if finalistLeft && champSlot}
      <line x1={CHAMP_LEFT_X + SLOT_W/2}  y1={CHAMP_Y + SLOT_H/2}
            x2={CHAMP_LEFT_X + SLOT_W/2}  y2={CHAMPION_Y - SLOT_H/2 - 4}
            stroke="#fbbf24" stroke-width="1" stroke-opacity="0.4" />
      <line x1={CHAMP_RIGHT_X + SLOT_W/2} y1={CHAMP_Y + SLOT_H/2}
            x2={CHAMP_RIGHT_X + SLOT_W/2} y2={CHAMPION_Y - SLOT_H/2 - 4}
            stroke="#fbbf24" stroke-width="1" stroke-opacity="0.4" />
      <line x1={CHAMP_LEFT_X + SLOT_W/2}  y1={CHAMPION_Y - SLOT_H/2 - 4}
            x2={CHAMP_RIGHT_X + SLOT_W/2} y2={CHAMPION_Y - SLOT_H/2 - 4}
            stroke="#fbbf24" stroke-width="1" stroke-opacity="0.4" />
      <line x1={CHAMPION_X + SLOT_W/2}    y1={CHAMPION_Y - SLOT_H/2 - 4}
            x2={CHAMPION_X + SLOT_W/2}    y2={CHAMPION_Y - SLOT_H/2}
            stroke="#fbbf24" stroke-width="1" stroke-opacity="0.4" />
    {/if}

    <!-- Championship label -->
    <text x={CHAMPION_X + SLOT_W/2} y={CHAMPION_Y - SLOT_H/2 - 8}
      font-size="8" text-anchor="middle" fill="#fbbf24" font-weight="700" letter-spacing="1.5"
    >🏆 CHAMPION</text>

    <!-- Finalist and champion slots rendered via BracketSlot -->
    {#if finalistLeft}
      <BracketSlot slot={finalistLeft} {activeRound} {eliminatedTeams} onclick={() => handleSlotClick(finalistLeft)} />
    {/if}
    {#if finalistRight}
      <BracketSlot slot={finalistRight} {activeRound} {eliminatedTeams} onclick={() => handleSlotClick(finalistRight)} />
    {/if}
    {#if champSlot}
      <BracketSlot slot={champSlot} {activeRound} {eliminatedTeams} onclick={() => handleSlotClick(champSlot)} />
    {/if}
    {/if}

  </svg>
</div>

<!-- Game info modal -->
{#if modalOpen && modalGame}
  <GameModal game={modalGame} onclose={closeModal} />
{/if}

<!-- Advance team modal -->
{#if advanceModalOpen && advanceContext}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="advance-backdrop" onclick={closeAdvanceModal}>
    <div class="advance-modal" onclick={(e) => e.stopPropagation()}>
      <div class="advance-header">
        <div>
          <span class="advance-label">{advanceContext.region} · {ROUND_DISPLAY[advanceContext.round]}</span>
          <h3>Who advances to the {advanceContext.targetRoundLabel}?</h3>
        </div>
        <button class="close-btn" onclick={closeAdvanceModal}>✕</button>
      </div>
      <p class="advance-hint">
        Select a team to manually advance. Hit <strong>Run Simulation</strong> to recalculate odds.
      </p>
      <div class="candidate-list">
        {#each advanceContext.candidates as candidate}
          <button class="candidate-btn" onclick={() => handleAdvance(candidate.name, advanceContext.gameId)}>
            <span class="cand-seed">#{candidate.seed}</span>
            <span class="cand-name">{candidate.name}</span>
            <span class="cand-prob">{(candidate.prob * 100).toFixed(1)}% to advance</span>
          </button>
        {:else}
          <p class="no-candidates">No candidates — lock earlier rounds first.</p>
        {/each}
      </div>
      {#if $pendingLocks[advanceContext.gameId]}
        <div class="locked-indicator">
          Currently locked: <strong>{$pendingLocks[advanceContext.gameId]}</strong>
        </div>
        <button class="remove-btn" onclick={() => handleRemove(advanceContext.gameId)}>
          Remove This Lock
        </button>
      {/if}
    </div>
  </div>
{/if}

{#if resultModalOpen && resultContext}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="advance-backdrop" onclick={() => { resultModalOpen = false; resultContext = null; }}>
    <div class="advance-modal" onclick={(e) => e.stopPropagation()}>
      <div class="advance-header">
        <div>
          <span class="advance-label">
            {ROUND_DISPLAY[resultContext.round] ?? `Round ${resultContext.round}`} · {resultContext.region}
          </span>
          <h3>
            {#if resultContext.winner}
              ✓ Result: {resultContext.winner}
            {:else}
              Mark Game Result
            {/if}
          </h3>
        </div>
        <button class="close-btn" onclick={() => { resultModalOpen = false; resultContext = null; }}>✕</button>
      </div>

      <p class="advance-hint">
        {#if resultContext.winner}
          This result is saved and affects all simulations. You can correct it or remove it.
        {:else}
          Select the team that won this game to lock in the real result.
        {/if}
      </p>

      <div class="candidate-list">
        {#each [resultContext.teamA, resultContext.teamB].filter(Boolean) as team}
          <button
            class="candidate-btn"
            class:current-winner={resultContext.winner === team}
            onclick={async () => {
              await setGameResult(resultContext.gameId, team);
              resultModalOpen = false;
              resultContext = null;
            }}
          >
            <span class="cand-name">{team}</span>
            {#if resultContext.winner === team}
              <span class="winner-badge">✓ Current Result</span>
            {:else}
              <span class="cand-prob">Mark as winner</span>
            {/if}
          </button>
        {/each}
      </div>

      {#if resultContext.winner}
        <button class="remove-btn" onclick={async () => {
          await clearSingleResult(resultContext.gameId);
          resultModalOpen = false;
          resultContext = null;
        }}>
          Remove This Result
        </button>
      {/if}
    </div>
  </div>
{/if}

<style>
  .bracket-svg-wrapper {
    width: 100%; overflow-x: auto; background: #0f1117;
    border-radius: 10px; border: 1px solid #2a3148;
  }
  .bracket-svg { display: block; min-width: 1000px; }
  .advance-backdrop {
    position: fixed; inset: 0; background: rgba(0,0,0,0.75);
    display: flex; align-items: center; justify-content: center;
    z-index: 200; backdrop-filter: blur(2px);
  }
  .advance-modal {
    background: #141824; border: 1px solid #2a3148; border-radius: 12px;
    width: 100%; max-width: 440px; padding: 1.5rem;
    display: flex; flex-direction: column; gap: 1rem;
  }
  .advance-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
  .advance-label { font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; display: block; margin-bottom: 0.2rem; }
  .advance-header h3 { font-size: 1.05rem; font-weight: 700; color: #f0f4ff; }
  .close-btn {
    background: #2a3148; border: 1px solid #3a4560; color: #e2e8f0;
    padding: 0.3rem 0.6rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; flex-shrink: 0;
  }
  .close-btn:hover { background: #3a4560; }
  .advance-hint { font-size: 0.8rem; color: #64748b; line-height: 1.5; }
  .candidate-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .candidate-btn {
    display: flex; align-items: center; gap: 0.75rem;
    background: #1e2538; border: 1px solid #2a3148; border-radius: 8px;
    padding: 0.75rem 1rem; cursor: pointer; text-align: left; width: 100%;
    transition: border-color 0.15s, background 0.15s;
  }
  .candidate-btn:hover { border-color: #3b82f6; background: #1a2744; }
  .cand-seed { font-size: 0.75rem; color: #64748b; min-width: 24px; }
  .cand-name { flex: 1; font-size: 0.9rem; font-weight: 600; color: #e2e8f0; }
  .cand-prob { font-size: 0.75rem; color: #4ade80; font-weight: 600; white-space: nowrap; }
  .no-candidates { font-size: 0.82rem; color: #475569; text-align: center; padding: 1rem; }
  .locked-indicator {
    font-size: 0.8rem; color: #fbbf24; background: #1f1a0e;
    border: 1px solid #78350f; border-radius: 6px; padding: 0.5rem 0.75rem;
  }
  .remove-btn {
    padding: 0.5rem 1rem; background: #2d1a00; border: 1px solid #f59e0b;
    color: #fbbf24; border-radius: 6px; font-size: 0.82rem; font-weight: 600;
    cursor: pointer; width: 100%; transition: background 0.15s;
  }
  .remove-btn:hover { background: #3d2400; }
  .current-winner {
      border-color: #4ade80 !important;
      background: #0f2010 !important;
  }
  .winner-badge {
      font-size: 0.75rem;
      color: #4ade80;
      font-weight: 600;
  }
</style>
