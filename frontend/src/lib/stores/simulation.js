import { writable, derived } from 'svelte/store';
import axios from 'axios';

//const API_BASE = 'http://localhost:8000';
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

export const simulationData = writable(null);
export const isLoading = writable(false);
export const error = writable(null);
export const lockedResults = writable({});
export const actualResults = writable({});

// Pending locks — applied locally before re-running simulation
// game_id -> team name, or round_key -> team name for future rounds
export const pendingLocks = writable({});
export const hasPendingChanges = writable(false);

export const teamsList = derived(simulationData, ($data) => {
    if (!$data?.teams) return [];
    return Object.entries($data.teams)
        .map(([name, stats]) => ({ name, ...stats }))
        .sort((a, b) => b.advancement.Champion - a.advancement.Champion);
});

export const matchupsList = derived(simulationData, ($data) => {
    if (!$data?.matchups) return [];
    return Object.entries($data.matchups).map(([id, matchup]) => ({
        game_id: id,
        ...matchup,
    }));
});

export const teamsByRegion = derived(simulationData, ($data) => {
    if (!$data?.teams) return {};
    const regions = { East: [], West: [], South: [], Midwest: [] };
    for (const [name, stats] of Object.entries($data.teams)) {
        if (regions[stats.region] !== undefined) {
            regions[stats.region].push({ name, ...stats });
        }
    }
    for (const region of Object.keys(regions)) {
        regions[region].sort((a, b) => a.seed - b.seed);
    }
    return regions;
});

export async function fetchSimulation() {
    isLoading.set(true);
    error.set(null);
    try {
        const res = await axios.get(`${API_BASE}/api/simulation`);
        simulationData.set(res.data);
        lockedResults.set(res.data.locked_results || {});
        pendingLocks.set(res.data.locked_results || {});
        hasPendingChanges.set(false);
        try {
            const resultsRes = await axios.get(`${API_BASE}/api/results`);
            actualResults.set(resultsRes.data.results || {});
        } catch (e) { console.error('Could not load results:', e); }
    } catch (e) {
        error.set('Failed to load simulation data. Is the backend running?');
        console.error(e);
    } finally {
        isLoading.set(false);
    }
}

export async function runSimulation() {
    isLoading.set(true);
    error.set(null);
    let currentPending = {};
    pendingLocks.subscribe(v => currentPending = v)();
    try {
        const res = await axios.post(`${API_BASE}/api/simulate`, {
            locked_results: currentPending,
        });
        simulationData.set(res.data);
        lockedResults.set(res.data.locked_results || {});
        pendingLocks.set(res.data.locked_results || {});
        hasPendingChanges.set(false);
    } catch (e) {
        error.set('Simulation failed. Check the backend.');
        console.error(e);
    } finally {
        isLoading.set(false);
    }
}

// Advance a team locally — does NOT trigger simulation
// gameId: the game_id this team wins
// winner: team name
export function advanceTeam(gameId, winner) {
    pendingLocks.update(current => ({ ...current, [gameId]: winner }));
    hasPendingChanges.set(true);
}

// Remove a single advancement lock locally
export function removeAdvancement(gameId) {
    pendingLocks.update(current => {
        const next = { ...current };
        delete next[gameId];
        return next;
    });
    hasPendingChanges.update(() => {
        let pending = {};
        pendingLocks.subscribe(v => pending = v)();
        return Object.keys(pending).length > 0;
    });
}

// Clear all pending locks locally
export function clearAllLocks() {
    pendingLocks.set({});
    hasPendingChanges.set(false);
}

export async function unlockAll() {
    isLoading.set(true);
    error.set(null);
    try {
        const res = await axios.post(`${API_BASE}/api/simulate`, {
            locked_results: {},
        });
        simulationData.set(res.data);
        lockedResults.set({});
        pendingLocks.set({});
        hasPendingChanges.set(false);
    } catch (e) {
        error.set('Failed to unlock all games.');
        console.error(e);
    } finally {
        isLoading.set(false);
    }
}

// Compute matchup stats for any two teams on demand (no simulation)
export async function fetchMatchup(teamA, teamB) {
    try {
        const res = await axios.post(`${API_BASE}/api/matchup`, {
            team_a: teamA,
            team_b: teamB,
        });
        return res.data;
    } catch (e) {
        console.error('Matchup fetch failed:', e);
        return null;
    }
}

export async function setGameResult(gameId, winner) {
    isLoading.set(true);
    error.set(null);
    try {
        const res = await axios.post(`${API_BASE}/api/results/set`, {
            game_id: gameId,
            winner,
        });
        simulationData.set(res.data);
        actualResults.set(res.data.actual_results || {});
        lockedResults.set(res.data.locked_results || {});
        pendingLocks.set(res.data.locked_results || {});
        hasPendingChanges.set(false);
    } catch (e) {
        error.set('Failed to save result.');
        console.error(e);
    } finally {
        isLoading.set(false);
    }
}

export async function clearSingleResult(gameId) {
    isLoading.set(true);
    error.set(null);
    try {
        const res = await axios.delete(`${API_BASE}/api/results/single?game_id=${gameId}`);
        actualResults.set(res.data.actual_results || {});
        await runSimulation();
    } catch (e) {
        error.set('Failed to clear result.');
        console.error(e);
    } finally {
        isLoading.set(false);
    }
}

export async function clearAllActualResults() {
    isLoading.set(true);
    error.set(null);
    try {
        const res = await axios.delete(`${API_BASE}/api/results/clear`);
        simulationData.set(res.data);
        actualResults.set({});
        lockedResults.set(res.data.locked_results || {});
        pendingLocks.set(res.data.locked_results || {});
        hasPendingChanges.set(false);
    } catch (e) {
        error.set('Failed to clear results.');
        console.error(e);
    } finally {
        isLoading.set(false);
    }
}

export async function lockGame(gameId, winner) {
    isLoading.set(true);
    error.set(null);
    try {
        const res = await axios.post(`${API_BASE}/api/lock`, {
            game_id: gameId,
            winner: winner ?? null,
        });
        simulationData.set(res.data);
        lockedResults.set(res.data.locked_results || {});
        pendingLocks.set(res.data.locked_results || {});
        hasPendingChanges.set(false);
    } catch (e) {
        error.set('Failed to lock game. Check the backend.');
        console.error(e);
    } finally {
        isLoading.set(false);
    }
}