"""
models.py — Pydantic models and dataclasses for MemSim
All request/response schemas live here.
"""
from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from dataclasses import dataclass, field


# ─────────────────────────────────────────────
# Core simulation types
# ─────────────────────────────────────────────

Strategy = Literal["first_fit", "best_fit", "worst_fit"]
Action   = Literal["allocate", "free"]


@dataclass
class Block:
    """A single contiguous memory region."""
    start:          int
    size:           int
    status:         str          # "free" | "used"
    pid:            Optional[str] = None
    requested_size: Optional[int] = None   # for internal fragmentation

    @property
    def end(self) -> int:
        return self.start + self.size - 1

    @property
    def internal_frag(self) -> int:
        """Wasted bytes inside an allocated block."""
        if self.status == "used" and self.requested_size is not None:
            return self.size - self.requested_size
        return 0

    def to_dict(self) -> dict:
        return {
            "start":          self.start,
            "end":            self.end,
            "size":           self.size,
            "status":         self.status,
            "pid":            self.pid,
            "requested_size": self.requested_size,
            "internal_frag":  self.internal_frag,
        }


@dataclass
class SimState:
    """Full simulator state — one object, mutated in place."""
    total_size:   int
    blocks:       List[Block]           = field(default_factory=list)
    event_log:    List[dict]            = field(default_factory=list)
    frag_history: List[dict]            = field(default_factory=list)
    tick:         int                   = 0
    seed:         Optional[int]         = None
    preset_name:  Optional[str]         = None


# ─────────────────────────────────────────────
# Request schemas
# ─────────────────────────────────────────────

class BlockInput(BaseModel):
    start:  int
    size:   int
    status: Literal["free", "used"] = "free"
    pid:    Optional[str] = None

class InitRequest(BaseModel):
    mode:       Literal["seed", "manual", "preset"]
    total_size: Optional[int] = 1024
    seed:       Optional[int] = None
    blocks:     Optional[List[BlockInput]] = None
    preset:     Optional[str] = None

class AllocateRequest(BaseModel):
    pid:            str
    size:           int
    strategy:       Strategy = "first_fit"
    requested_size: Optional[int] = None  # if different from size (internal frag demo)

class FreeRequest(BaseModel):
    pid: str

class ProcessStep(BaseModel):
    pid:      str
    size:     int = 0
    action:   Action
    strategy: Strategy = "first_fit"

class BatchRequest(BaseModel):
    processes: List[ProcessStep]

class CompareRequest(BaseModel):
    init:     InitRequest
    workload: List[ProcessStep]


# ─────────────────────────────────────────────
# Response helpers
# ─────────────────────────────────────────────

def block_list(blocks: List[Block]) -> List[dict]:
    return [b.to_dict() for b in blocks]