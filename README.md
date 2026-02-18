# MEMSIM — Contiguous Memory Allocation Simulator

A full-stack interactive simulator for OS-style contiguous memory allocation.

## Features

- **Three allocation strategies**: First Fit, Best Fit, Worst Fit
- **Allocation unit rounding**: Simulates physical vs logical size (internal fragmentation)
- **Deallocation** with automatic block coalescing
- **Compaction** to eliminate external fragmentation
- **Live D3.js memory map** — visual horizontal strip with tooltips
- **Step-by-step trace** — navigate through every allocation event
- **Real-time metrics**:
  - Internal fragmentation per block
  - External fragmentation (scattered free space)
  - Total free / allocated memory
  - Largest free block
  - Memory utilization %
- **Black & white brutalist UI** with shadow-hover buttons
- **Demo scenarios**: Fragmented, Near-Full, Swiss Cheese

## Project Structure

```
memsim/
├── backend/
│   ├── simulator.py   ← Core allocation engine
│   └── main.py        ← FastAPI REST API
├── frontend/
│   └── index.html     ← D3.js UI (single file, served by FastAPI)
├── requirements.txt
└── run.bat
```

## Setup & Run

### Prerequisites
- Python 3.9 - 3.13
- pip

### Install & Start

```bash
cd memsim
pip install -r requirements.txt
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Then open: **http://localhost:8000**

Or use the convenience script:
```bash
bash run.sh
```

## REST API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/state` | Full memory state + metrics |
| POST | `/api/allocate` | Allocate memory for a PID |
| POST | `/api/free` | Free memory for a PID |
| POST | `/api/compact` | Run compaction |
| POST | `/api/reset` | Reset simulator |
| GET | `/api/log` | Full event log |
| GET | `/api/metrics` | Fragmentation metrics only |

### POST /api/allocate
```json
{
  "pid": "P1",
  "size": 100,
  "strategy": "first_fit"  // first_fit | best_fit | worst_fit
}
```

### POST /api/free
```json
{ "pid": "P1" }
```

### POST /api/reset
```json
{
  "total_size": 1024,
  "allocation_unit": 32
}
```

## How It Works

### Allocation Unit Rounding
When a process requests N KB, the simulator rounds up to the nearest multiple of the allocation unit:
```
physical_size = ceil(N / unit) * unit
internal_fragmentation = physical_size - N
```

### Fragmentation Metrics
- **Internal fragmentation**: Wasted space inside allocated blocks (rounding overhead)
- **External fragmentation**: Free space that exists but is too scattered to satisfy requests
  - `external_frag = total_free - largest_free_block`

### Strategies
| Strategy | Picks |
|----------|-------|
| First Fit | First hole ≥ request |
| Best Fit | Smallest hole ≥ request |
| Worst Fit | Largest hole ≥ request |
