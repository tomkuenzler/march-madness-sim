<script>
  import { onMount } from 'svelte';
  import { 
      fetchSimulation, runSimulation, unlockAll, clearAllLocks,
      isLoading, error, simulationData, 
      lockedResults, pendingLocks, hasPendingChanges, clearAllActualResults, actualResults 
  } from '$lib/stores/simulation.js';
  import Bracket from '$lib/components/Bracket.svelte';

  onMount(() => {
    fetchSimulation();
  });

  function handleRerun() {
    runSimulation();
  }
</script>

<div class="app">
  <header>
    <div class="header-left">
      <h1>🏀 March Madness Simulator</h1>
      <span class="subtitle">Monte Carlo · 10,000 simulations · KenPom data</span>
    </div>
    <div class="header-right">
      {#if $error}
        <span class="error-msg">{$error}</span>
      {/if}
      {#if Object.keys($lockedResults).length > 0}
        <button class="unlock-all-btn" onclick={unlockAll} disabled={$isLoading}>
          🔓 Unlock All ({Object.keys($lockedResults).length})
        </button>
      {/if}
      {#if $hasPendingChanges}
          <button class="clear-btn" onclick={clearAllLocks} disabled={$isLoading}>
              🗑 Clear Bracket
          </button>
      {/if}
            {#if Object.keys($actualResults).length > 0}
        <button class="results-btn" onclick={clearAllActualResults} disabled={$isLoading}>
          🗑 Clear Results ({Object.keys($actualResults).length})
        </button>
      {/if}
      <button class="rerun-btn" onclick={handleRerun} disabled={$isLoading}>
        {#if $isLoading}
          <span class="spinner"></span>
        {:else}
          ▶ Run Simulation
        {/if}
      </button>
    </div>
  </header>
  {#if $hasPendingChanges}
      <div class="pending-banner">
          ⚠ Bracket has unsaved changes — hit <strong>Run Simulation</strong> to update odds
      </div>
  {/if}

  <main>
    {#if $isLoading && !$error}
      <div class="loading-screen">
        <span class="spinner large"></span>
        <p>Running 10,000 simulations...</p>
      </div>
    {:else if $error}
      <div class="error-screen">
        <p>⚠️ {$error}</p>
        <p class="hint">Make sure the FastAPI backend is running on port 8000.</p>
      </div>
    {:else}
      <Bracket />
    {/if}
  </main>
</div>

<style>
  :global(*, *::before, *::after) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(body) {
    background-color: #0f1117;
    color: #e2e8f0;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    min-height: 100vh;
  }

  :global(::-webkit-scrollbar) {
    width: 6px;
    height: 6px;
  }
  :global(::-webkit-scrollbar-track) { background: #1a1f2e; }
  :global(::-webkit-scrollbar-thumb) { background: #3a4560; border-radius: 3px; }

  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 2rem;
    background: #141824;
    border-bottom: 1px solid #2a3148;
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .header-left h1 {
    font-size: 1.4rem;
    font-weight: 700;
    color: #f0f4ff;
    letter-spacing: -0.02em;
  }

  .pending-banner {
      background: #1c1a00;
      border-bottom: 1px solid #ca8a04;
      color: #fde68a;
      padding: 0.6rem 2rem;
      font-size: 0.82rem;
      text-align: center;
  }

  .subtitle {
    font-size: 0.75rem;
    color: #64748b;
    margin-top: 0.15rem;
    display: block;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .error-msg {
    font-size: 0.8rem;
    color: #f87171;
  }

  .unlock-all-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1.2rem;
    background: #2d1a00;
    border: 1px solid #f59e0b;
    color: #fbbf24;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
  }
  .unlock-all-btn:hover:not(:disabled) { background: #3d2400; }
  .unlock-all-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  .clear-btn {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 1.2rem;
      background: transparent;
      border: 1px solid #475569;
      color: #94a3b8;
      border-radius: 6px;
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      transition: border-color 0.2s, color 0.2s;
  }

  .clear-btn:hover:not(:disabled) {
      border-color: #ef4444;
      color: #ef4444;
  }

  .clear-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  .results-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1.2rem;
    background: transparent;
    border: 1px solid #ef4444;
    color: #f87171;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
  }
  .results-btn:hover:not(:disabled) { background: #1a0a0a; }
  .results-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  .rerun-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: #3b82f6;
    color: white;
    border: none;
    padding: 0.5rem 1.2rem;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s;
  }

  .rerun-btn:hover:not(:disabled) { background: #2563eb; }
  .rerun-btn:disabled {
    background: #1e3a5f;
    color: #64748b;
    cursor: not-allowed;
  }

  main {
    flex: 1;
    padding: 1.5rem;
    overflow-x: auto;
  }

  .loading-screen, .error-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 60vh;
    gap: 1rem;
    color: #64748b;
  }

  .error-screen { color: #f87171; }
  .hint { font-size: 0.8rem; color: #475569; }

  :global(.spinner) {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid #3b82f6;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  :global(.spinner.large) {
    width: 36px;
    height: 36px;
    border-width: 3px;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>