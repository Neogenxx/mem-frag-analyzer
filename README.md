# MemSim — Contiguous Memory Allocation Simulator

> An academic Operating Systems project that makes memory allocation visual, measurable, and reproducible.

---

## Overview

MemSim is a browser-based simulator that demonstrates how an operating system manages contiguous memory allocation. It implements the three core allocation strategies taught in OS theory First Fit, Best Fit, and Worst Fit and makes their behavior observable through real-time visualization, metrics, and side-by-side comparison.

Built as part of the B.Tech Semester 4 Operating Systems course.

---

## Problem Statement

Memory management is one of the most fundamental concepts in Operating Systems. However, studying it from a textbook leaves a critical gap  you can read about fragmentation but you cannot see it happen. You can memorize the three fit strategies but you cannot observe how differently they behave on the same workload.

MemSim was built to close that gap.

---

## Project Goals

- Simulate contiguous memory allocation with dynamic partitioning
- Implement and compare First Fit, Best Fit, and Worst Fit strategies
- Visualize memory layout, fragmentation, and allocation behavior in real time
- Make every simulation reproducible using a seed-based system
- Generate academic reports from simulation results

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | Vanilla JavaScript, D3.js |
| Visualization | D3.js (SVG-based memory map and graphs) |
| PDF Export | ReportLab |
| Server | Uvicorn |

---

## Project Structure

```
memsim/
├── backend/
│   ├── main.py          ← FastAPI app, all API endpoints
│   ├── models.py        ← Pydantic schemas, Block and SimState dataclasses
│   ├── allocator.py     ← First Fit, Best Fit, Worst Fit, Compaction, Init
│   ├── metrics.py       ← Fragmentation and memory metrics computation
│   └── export_pdf.py    ← PDF report generation
├── frontend/
│   └── index.html       ← Complete single-file UI with D3.js
└── requirements.txt
```

---


## Features

- First Fit, Best Fit, Worst Fit allocation
- Visual memory map with address scale and tooltips
- Batch workload execution with timeline playback
- Fragmentation over time graph
- Strategy comparison: same workload, all three strategies, side by side
- Compaction with animation
- PDF report export
- Seed-based reproducible simulation
---

## Metrics

| Metric | Formula | Meaning |
|---|---|---|
| External Fragmentation | `1 - (largest free block / total free space)` | How scattered the free space is |
| Internal Fragmentation | `block size - requested size` | Wasted space inside allocated blocks |
| Memory Utilization | `used space / total size` | Percentage of RAM in use |
| Largest Free Block | Max size of any single free region | Maximum allocatable request size |
| Free Space | Sum of all free block sizes | Total available bytes |
| Failed Allocations | Count of requests with no suitable block | Allocation failure rate |

> External fragmentation formula source: Silberschatz, Galvin & Gagne — Operating System Concepts, 10th Edition

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/memory/init` | Initialize memory (seed / preset / manual) |
| GET | `/memory/presets` | List available preset configurations |
| POST | `/memory/allocate` | Allocate a single process |
| DELETE | `/memory/free/{pid}` | Free all blocks belonging to a PID |
| POST | `/memory/compact` | Compact memory |
| POST | `/memory/batch` | Run a batch workload |
| POST | `/memory/compare` | Compare all three strategies |
| GET | `/memory/state` | Get full current state snapshot |
| GET | `/memory/export-state` | Export state as JSON |
| POST | `/export/pdf` | Generate and download PDF report |

---

## Setup and Installation

### Requirements
- Python 3.10 or higher
- pip

### Install Dependencies

```bash
pip install -r requirements.txt
```



### Run the Server

```bash
cd backend
uvicorn main:app --reload
```

### Open the App

```
http://127.0.0.1:8000
```
---

## Key Academic Findings

Running the simulator with different seeds and workloads demonstrates several important OS concepts:

**Finding 1 — No strategy is universally best**
On certain workloads Worst Fit can achieve lower external fragmentation than Best Fit or First Fit. Strategy performance depends entirely on process sizes and order.

**Finding 2 — Total free space is misleading**
A system can have 260B free but fail to allocate a 150B request if free space is fragmented across 5 small holes. The largest free block is more important than total free space.

**Finding 3 — Best Fit minimizes failed allocations**
By carefully matching requests to the tightest fitting block, Best Fit tends to preserve larger free blocks for bigger future requests, resulting in fewer allocation failures.

**Finding 4 — Compaction completely resolves external fragmentation**
After compaction, all free space merges into one contiguous block. External fragmentation drops to 0%. The cost is that all processes must be paused and relocated.

---

## Concepts Demonstrated

| OS Concept | How MemSim Demonstrates It |
|---|---|
| First Fit | Visible scan from address 0, leftover fragment shown |
| Best Fit | Tightest block selected, tiny remainders created |
| Worst Fit | Largest block consumed first each time |
| External Fragmentation | Scattered holes visible on memory map, percentage measured |
| Internal Fragmentation | Dark strip inside block when requested size < block size |
| Coalescing | Adjacent free blocks automatically merge on free |
| Compaction | Animated block movement, fragmentation drops to 0% |
| Memory Utilization | Tracked over time on fragmentation graph |
| Allocation Failure | Logged as FAIL when no suitable block exists |
