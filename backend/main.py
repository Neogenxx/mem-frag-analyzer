"""
main.py — MemSim FastAPI application.
Run with: uvicorn main:app --reload
"""
from __future__ import annotations
import copy
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
import os

from models import (
    SimState, InitRequest, AllocateRequest, FreeRequest,
    BatchRequest, CompareRequest, block_list
)
from allocator import (
    init_from_seed, init_from_manual, init_from_preset,
    allocate, free_pid, compact, PRESETS
)
from metrics import compute_metrics, snapshot, metrics_from_blocks
from export_pdf import generate_pdf

app = FastAPI(title="MemSim", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global simulation state ────────────────────────────────────────────────
# One state object for the session. In a real multi-user system you'd use
# a session ID, but for academic purposes this is fine.
state = SimState(total_size=1024)


def _full_response() -> dict:
    """Standard full state response returned after every mutation."""
    return {
        "total_size":    state.total_size,
        "blocks":        block_list(state.blocks),
        "metrics":       compute_metrics(state),
        "event_log":     state.event_log,
        "frag_history":  state.frag_history,
        "tick":          state.tick,
        "seed":          state.seed,
        "preset_name":   state.preset_name,
    }


# ── Initialization ─────────────────────────────────────────────────────────

@app.get("/memory/presets")
def list_presets():
    """List available preset names and their descriptions."""
    return {
        "presets": [
            {"name": "clean",       "description": "Single large free block",      "total_size": 1024},
            {"name": "fragmented",  "description": "Heavily fragmented layout",    "total_size": 1024},
            {"name": "uniform",     "description": "8 equal free blocks",          "total_size": 1024},
            {"name": "mostly_used", "description": "Most memory allocated",        "total_size": 512},
        ]
    }


@app.post("/memory/init")
def init_memory(req: InitRequest):
    """
    Initialize memory. Three modes:
    - seed:   deterministic random layout
    - manual: explicit block list
    - preset: named predefined layout
    """
    global state

    if req.mode == "seed":
        seed = req.seed if req.seed is not None else 0
        total = req.total_size or 1024
        blocks = init_from_seed(total, seed)
        state = SimState(total_size=total, blocks=blocks, seed=seed)

    elif req.mode == "manual":
        if not req.blocks:
            raise HTTPException(400, "blocks required for manual mode")
        total = req.total_size or 1024
        try:
            blocks = init_from_manual(total, [b.model_dump() for b in req.blocks])
        except ValueError as e:
            raise HTTPException(400, str(e))
        state = SimState(total_size=total, blocks=blocks)

    elif req.mode == "preset":
        name = req.preset or "clean"
        try:
            total, blocks = init_from_preset(name)
        except ValueError as e:
            raise HTTPException(400, str(e))
        state = SimState(total_size=total, blocks=blocks, preset_name=name)

    else:
        raise HTTPException(400, f"Unknown mode: {req.mode}")

    # Take initial snapshot
    snapshot(state, label="init")
    return _full_response()


# ── Single operations ──────────────────────────────────────────────────────

@app.post("/memory/allocate")
def allocate_process(req: AllocateRequest):
    """Allocate a single process with a named strategy."""
    result = allocate(
        state, req.pid, req.size, req.strategy,
        requested_size=req.requested_size
    )
    snapshot(state, label=f"alloc({req.pid})")
    return {**result, **_full_response()}


@app.delete("/memory/free/{pid}")
def free_process(pid: str):
    """Free all memory held by a PID."""
    result = free_pid(state, pid)
    snapshot(state, label=f"free({pid})")
    return {**result, **_full_response()}


@app.post("/memory/compact")
def compact_memory():
    """Compact memory — move all used blocks to front, free space to end."""
    result = compact(state)
    snapshot(state, label="compact")
    return {**result, **_full_response()}


# ── Batch execution ────────────────────────────────────────────────────────

@app.post("/memory/batch")
def batch_execute(req: BatchRequest):
    """
    Run a list of processes sequentially.
    Returns per-step results + fragmentation history for timeline replay.
    Resets frag_history so the graph shows only this batch run.
    """
    state.frag_history = []   # clear old history — each batch is a fresh graph
    state.tick = 0             # reset tick counter for clean event labels

    steps = []
    for proc in req.processes:
        if proc.action == "allocate":
            r = allocate(state, proc.pid, proc.size, proc.strategy)
        else:  # free
            r = free_pid(state, proc.pid)

        snap = snapshot(state, label=f"{proc.action}({proc.pid})")
        steps.append({
            **r,
            "blocks_after":  block_list(state.blocks),
            "metrics_after": compute_metrics(state),
            "snap":          snap,
        })

    return {
        "steps":        steps,
        "frag_history": state.frag_history,
        **_full_response(),
    }


# ── Strategy comparison ────────────────────────────────────────────────────

@app.post("/memory/compare")
def compare_strategies(req: CompareRequest):
    """
    Run the same workload with First Fit, Best Fit, and Worst Fit.
    Uses isolated state — does NOT mutate the global state.
    """
    results = {}

    for strategy in ["first_fit", "best_fit", "worst_fit"]:
        # Build a fresh isolated state
        init_req = req.init
        if init_req.mode == "seed":
            seed = init_req.seed or 0
            total = init_req.total_size or 1024
            blocks = init_from_seed(total, seed)
            sim = SimState(total_size=total, blocks=blocks, seed=seed)
        elif init_req.mode == "preset":
            name = init_req.preset or "clean"
            total, blocks = init_from_preset(name)
            sim = SimState(total_size=total, blocks=blocks)
        else:
            total = init_req.total_size or 1024
            blocks = init_from_manual(total, [b.model_dump() for b in (init_req.blocks or [])])
            sim = SimState(total_size=total, blocks=blocks)

        failed = 0
        frag_hist = []

        for proc in req.workload:
            if proc.action == "allocate":
                r = allocate(sim, proc.pid, proc.size, strategy)
                if not r["success"]:
                    failed += 1
            else:
                free_pid(sim, proc.pid)

            snap = snapshot(sim, label=f"{proc.action}({proc.pid})")
            frag_hist.append(snap)

        m = compute_metrics(sim)
        results[strategy] = {
            **m,
            "failed_allocs": failed,
            "final_blocks":  block_list(sim.blocks),
            "frag_history":  frag_hist,
            "total_size":    sim.total_size,
        }

    return {
        "seed":       req.init.seed,
        "strategies": results,
    }


# ── State inspection ───────────────────────────────────────────────────────

@app.get("/memory/state")
def get_state():
    return _full_response()


@app.get("/memory/metrics")
def get_metrics():
    return compute_metrics(state)


@app.get("/memory/export-state")
def export_state():
    """Export current memory state as JSON (for reproducibility)."""
    return {
        "total_size": state.total_size,
        "seed":       state.seed,
        "blocks": [
            {"start": b.start, "size": b.size,
             "status": b.status, "pid": b.pid}
            for b in state.blocks
        ]
    }


# ── PDF export ─────────────────────────────────────────────────────────────

@app.post("/export/pdf")
def export_pdf(data: dict):
    """Generate and stream a PDF report."""
    try:
        pdf_bytes = generate_pdf(data)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="memsim_report.pdf"'}
    )


# ── Serve frontend ─────────────────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")