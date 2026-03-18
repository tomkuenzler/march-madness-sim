# March Madness Monte Carlo Simulator

A full-stack NCAA Tournament bracket simulator using KenPom efficiency data and Monte Carlo methods.

**Stack:** Python (FastAPI) + Svelte

---

## Backend Setup

### 1. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Add your KenPom data
Replace `backend/data/kenpom.csv` with your own TableCapture export.

**Required CSV columns:**
| Column | Description |
|--------|-------------|
| `Team` | Team name |
| `AdjEM` | Net Rating (adjusted efficiency margin) |
| `AdjO` | Adjusted offensive efficiency |
| `AdjD` | Adjusted defensive efficiency |
| `AdjT` | Adjusted tempo |
| `Seed` | Tournament seed (1–16) |
| `Region` | One of: `East`, `West`, `South`, `Midwest` |

> **Note:** Column names `NetRTG`, `OE`, `DE`, `Tempo` are also accepted and will be auto-mapped.

The CSV must contain exactly **64 rows** — 16 teams per region.

### 3. Run the API
```bash
uvicorn main:app --reload --port 8000
```

API will be available at `http://localhost:8000`

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Server status |
| GET | `/api/teams` | Raw team stats |
| GET | `/api/simulation` | Cached simulation results |
| POST | `/api/simulate` | Re-run with optional locked results |
| POST | `/api/lock` | Lock/unlock a single game winner |

### POST /api/simulate — Request body
```json
{
  "locked_results": {
    "East_R1_G1": "UCSB",
    "West_R2_G3": "Oregon"
  },
  "n_simulations": 10000
}
```

### POST /api/lock — Request body
```json
{
  "game_id": "East_R1_G1",
  "winner": "UCSB"
}
```
Send `"winner": null` to unlock a game.

---

## Game ID Format

Games are identified by:
- `{Region}_R{Round}_G{Game}` — e.g. `East_R1_G1`, `West_R3_G2`
- `FF_G1`, `FF_G2` — Final Four games
- `Championship` — the title game

Round numbers: 1=R64, 2=R32, 3=Sweet16, 4=Elite8, 5=FinalFour, 6=Championship

---

## Win Probability Formula

```
point_diff = (NetRTG_A - NetRTG_B) * (Tempo_A + Tempo_B) / 200
win_prob_A = 1 / (1 + e^(-0.3 * point_diff))
```

The logistic scale factor `k=0.3` maps spreads to win probabilities consistent with historical NCAA tournament results (e.g. a 10-point favorite wins ~95% of the time).

---

## Frontend Setup (coming next)
```bash
cd frontend
npm install
npm run dev
```
