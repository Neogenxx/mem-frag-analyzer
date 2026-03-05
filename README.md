# MemSim — Contiguous Memory Allocation Simulator

Academic OS project. FastAPI backend + D3.js frontend.

## Project Structure

```
memsim/
├── backend/
│   ├── main.py         ← FastAPI app, all endpoints
│   ├── models.py       ← Pydantic request/response schemas + Block dataclass
│   ├── allocator.py    ← First Fit, Best Fit, Worst Fit, Compaction, Init
│   ├── metrics.py      ← Fragmentation metrics computation
│   └── export_pdf.py   ← PDF report generation (reportlab)
├── frontend/
│   └── index.html      ← Complete single-file UI (D3.js, no build step)
└── requirements.txt
```

## Setup & Run

```bash
# 1. Install dependencies
cd memsim
pip install -r requirements.txt

# 2. Start backend
cd backend
uvicorn main:app --reload

# 3. Open frontend
# Visit http://localhost:8000
# The backend serves the frontend automatically.
# For dev: open frontend/index.html directly and set API = 'http://localhost:8000' in JS.
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET    | /memory/presets | List preset names |
| POST   | /memory/init | Initialize (seed / manual / preset) |
| POST   | /memory/allocate | Allocate single process |
| DELETE | /memory/free/{pid} | Free a process |
| POST   | /memory/compact | Compact memory |
| POST   | /memory/batch | Run workload, returns timeline steps |
| POST   | /memory/compare | Compare all 3 strategies |
| GET    | /memory/state | Full state snapshot |
| GET    | /memory/export-state | Export state as JSON |
| POST   | /export/pdf | Download PDF report |

## Key Design Decisions

- **One global SimState** per server session. Simple and sufficient for academic use.
- **Seed reproducibility**: `random.Random(seed)` gives identical layouts every time.
- **Pure allocator functions**: `first_fit`, `best_fit`, `worst_fit` have no side effects.
- **`/compare` uses isolated state**: never mutates global state; runs 3 fresh simulations.
- **Event log never has undefined**: `log_event()` always writes all fields.
- **Frontend is one HTML file**: no build step, no npm, works by opening the file.

## External Fragmentation Formula

```
external_frag = 1 - (largest_free_block / total_free_space)
```

- 0.0 = ideal (all free space is one contiguous block)
- 1.0 = worst (free space is completely scattered)

Source: Silberschatz, Galvin & Gagne — Operating System Concepts, 10th ed.

## Example: Reproduce a Simulation

```json
POST /memory/init
{
  "mode": "seed",
  "seed": 42,
  "total_size": 1024
}
```

The same seed always produces the same layout. Share the seed to reproduce results.