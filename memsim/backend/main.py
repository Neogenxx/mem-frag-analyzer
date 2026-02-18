"""
FastAPI backend for Contiguous Memory Allocation Simulator
"""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import os

from simulator import MemorySimulator

app = FastAPI(title="Memory Allocation Simulator", version="1.0.0")

# Global simulator instance
sim = MemorySimulator(total_size=1024, allocation_unit=32)


# ─── Request / Response Models ────────────────────────────────────────────────

class AllocateRequest(BaseModel):
    pid: str = Field(..., description="Process ID")
    size: int = Field(..., gt=0, description="Logical size in KB")
    strategy: str = Field("first_fit", description="first_fit | best_fit | worst_fit")

class FreeRequest(BaseModel):
    pid: str = Field(..., description="Process ID to free")

class ResetRequest(BaseModel):
    total_size: Optional[int] = Field(None, gt=0, description="Total memory in KB")
    allocation_unit: Optional[int] = Field(None, gt=0, description="Allocation unit in KB")


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/state")
def get_state():
    return sim.get_state()

@app.post("/api/allocate")
def allocate(req: AllocateRequest):
    strategy = req.strategy.lower()
    if strategy == "first_fit":
        result = sim.allocate_first_fit(req.pid, req.size)
    elif strategy == "best_fit":
        result = sim.allocate_best_fit(req.pid, req.size)
    elif strategy == "worst_fit":
        result = sim.allocate_worst_fit(req.pid, req.size)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")
    return {
        "result": result.to_dict(),
        "state": sim.get_state(),
    }

@app.post("/api/free")
def free_memory(req: FreeRequest):
    success, message = sim.free(req.pid)
    return {
        "success": success,
        "message": message,
        "state": sim.get_state(),
    }

@app.post("/api/compact")
def compact():
    message = sim.compact()
    return {
        "message": message,
        "state": sim.get_state(),
    }

@app.post("/api/reset")
def reset(req: ResetRequest = None):
    if req:
        sim.reset(req.total_size, req.allocation_unit)
    else:
        sim.reset()
    return {
        "message": "Memory reset",
        "state": sim.get_state(),
    }

@app.get("/api/log")
def get_log():
    return {"log": sim.event_log}

@app.get("/api/metrics")
def get_metrics():
    return sim.get_metrics().to_dict()

# ─── Static Frontend ──────────────────────────────────────────────────────────

static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def root():
    html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())
