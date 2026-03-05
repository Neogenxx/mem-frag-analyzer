"""
allocator.py — Pure allocation functions + compaction + initialization.
No side effects — all functions take state and return results.
"""
from __future__ import annotations
import random
import copy
from typing import Optional, List, Tuple

from models import Block, SimState, Strategy


# ─────────────────────────────────────────────
# Initialization
# ─────────────────────────────────────────────

PRESETS = {
    "clean": {
        "total_size": 1024,
        "blocks": [
            {"start": 0, "size": 1024, "status": "free"},
        ]
    },
    "fragmented": {
        "total_size": 1024,
        "blocks": [
            {"start": 0,   "size": 100, "status": "used", "pid": "P1"},
            {"start": 100, "size": 50,  "status": "free"},
            {"start": 150, "size": 200, "status": "used", "pid": "P2"},
            {"start": 350, "size": 30,  "status": "free"},
            {"start": 380, "size": 150, "status": "used", "pid": "P3"},
            {"start": 530, "size": 40,  "status": "free"},
            {"start": 570, "size": 180, "status": "used", "pid": "P4"},
            {"start": 750, "size": 274, "status": "free"},
        ]
    },
    "uniform": {
        "total_size": 1024,
        "blocks": [{"start": i * 128, "size": 128, "status": "free"} for i in range(8)]
    },
    "mostly_used": {
        "total_size": 512,
        "blocks": [
            {"start": 0,   "size": 100, "status": "used", "pid": "PA"},
            {"start": 100, "size": 20,  "status": "free"},
            {"start": 120, "size": 80,  "status": "used", "pid": "PB"},
            {"start": 200, "size": 10,  "status": "free"},
            {"start": 210, "size": 120, "status": "used", "pid": "PC"},
            {"start": 330, "size": 182, "status": "free"},
        ]
    }
}


def init_from_seed(total_size: int, seed: int) -> List[Block]:
    """Deterministic random layout from a seed."""
    rng = random.Random(seed)
    blocks: List[Block] = []
    pos = 0
    pid_counter = 1

    while pos < total_size:
        remaining = total_size - pos
        size = rng.randint(32, min(220, remaining))
        if remaining - size < 16:   # avoid tiny tail fragments
            size = remaining

        is_used = rng.random() > 0.45
        pid = f"P{pid_counter}" if is_used else None
        if is_used:
            pid_counter += 1

        blocks.append(Block(
            start=pos, size=size,
            status="used" if is_used else "free",
            pid=pid
        ))
        pos += size

    return blocks


def init_from_manual(total_size: int, block_dicts: list) -> List[Block]:
    """User-defined explicit block layout. Validates contiguity."""
    blocks = []
    expected_start = 0
    for bd in sorted(block_dicts, key=lambda x: x["start"]):
        if bd["start"] != expected_start:
            raise ValueError(
                f"Gap or overlap at address {expected_start}. "
                f"Block starts at {bd['start']}."
            )
        b = Block(
            start=bd["start"], size=bd["size"],
            status=bd["status"], pid=bd.get("pid")
        )
        blocks.append(b)
        expected_start += bd["size"]
    if expected_start != total_size:
        raise ValueError(
            f"Blocks cover {expected_start} bytes but total_size is {total_size}."
        )
    return blocks


def init_from_preset(name: str) -> Tuple[int, List[Block]]:
    if name not in PRESETS:
        raise ValueError(f"Unknown preset '{name}'. Available: {list(PRESETS.keys())}")
    p = PRESETS[name]
    blocks = [
        Block(start=b["start"], size=b["size"],
              status=b["status"], pid=b.get("pid"))
        for b in p["blocks"]
    ]
    return p["total_size"], blocks


# ─────────────────────────────────────────────
# Fit strategies — pure functions
# ─────────────────────────────────────────────

def first_fit(blocks: List[Block], size: int) -> Optional[Block]:
    """Return first free block that fits."""
    for b in blocks:
        if b.status == "free" and b.size >= size:
            return b
    return None


def best_fit(blocks: List[Block], size: int) -> Optional[Block]:
    """Return smallest free block that fits (minimises leftover)."""
    candidates = [b for b in blocks if b.status == "free" and b.size >= size]
    return min(candidates, key=lambda b: b.size, default=None)


def worst_fit(blocks: List[Block], size: int) -> Optional[Block]:
    """Return largest free block (leaves the biggest remainder)."""
    candidates = [b for b in blocks if b.status == "free" and b.size >= size]
    return max(candidates, key=lambda b: b.size, default=None)


STRATEGIES = {
    "first_fit": first_fit,
    "best_fit":  best_fit,
    "worst_fit": worst_fit,
}


# ─────────────────────────────────────────────
# Allocation & freeing
# ─────────────────────────────────────────────

def _split_block(blocks: List[Block], target: Block,
                 pid: str, alloc_size: int, requested_size: int):
    """
    Replace target with an allocated block + optional remainder.
    Mutates the blocks list in place.
    """
    idx = blocks.index(target)
    blocks.pop(idx)

    allocated = Block(
        start=target.start, size=alloc_size,
        status="used", pid=pid,
        requested_size=requested_size
    )
    blocks.insert(idx, allocated)

    remainder = target.size - alloc_size
    if remainder > 0:
        blocks.insert(idx + 1, Block(
            start=target.start + alloc_size,
            size=remainder, status="free"
        ))


def allocate(state: SimState, pid: str, size: int,
             strategy_name: Strategy,
             requested_size: Optional[int] = None) -> dict:
    """
    Try to allocate `size` bytes for `pid` using the given strategy.
    requested_size < size can simulate internal fragmentation (e.g. fixed partitions).
    """
    fn = STRATEGIES.get(strategy_name, first_fit)
    target = fn(state.blocks, size)
    req_size = requested_size if requested_size is not None else size

    if target is None:
        _log(state, "FAIL", pid=pid, strategy=strategy_name, size=size,
             reason="No suitable block found")
        return {
            "success":  False,
            "pid":      pid,
            "strategy": strategy_name,
            "size":     size,
            "reason":   "No suitable block found",
        }

    chosen_start = target.start
    _split_block(state.blocks, target, pid, size, req_size)
    _log(state, "ALLOC", pid=pid, strategy=strategy_name,
         start=chosen_start, size=size)

    return {
        "success":   True,
        "pid":       pid,
        "strategy":  strategy_name,
        "start":     chosen_start,
        "size":      size,
        "end":       chosen_start + size - 1,
        "reason":    "",
    }


def free_pid(state: SimState, pid: str) -> dict:
    """Free all blocks belonging to pid and merge adjacent free blocks."""
    freed = []
    for b in state.blocks:
        if b.pid == pid:
            b.status = "free"
            b.pid = None
            b.requested_size = None
            freed.append(b.start)

    if not freed:
        _log(state, "FAIL", pid=pid, strategy="none",
             reason=f"PID {pid} not found")
        return {"success": False, "pid": pid, "reason": f"PID {pid} not found"}

    _merge_free(state.blocks)
    _log(state, "FREE", pid=pid, strategy="none")
    return {"success": True, "pid": pid, "freed_starts": freed}


def _merge_free(blocks: List[Block]):
    """Coalesce adjacent free blocks. Mutates list in place."""
    i = 0
    while i < len(blocks) - 1:
        if blocks[i].status == "free" and blocks[i + 1].status == "free":
            blocks[i].size += blocks[i + 1].size
            blocks.pop(i + 1)
        else:
            i += 1


# ─────────────────────────────────────────────
# Compaction
# ─────────────────────────────────────────────

def compact(state: SimState) -> dict:
    """
    Move all used blocks to the front, collect free space at the end.
    Returns before/after block lists for animation.
    """
    before = [copy.copy(b) for b in state.blocks]

    used   = [b for b in state.blocks if b.status == "used"]
    total_used = sum(b.size for b in used)
    total_free = state.total_size - total_used

    new_blocks: List[Block] = []
    pos = 0
    for b in used:
        new_b = Block(start=pos, size=b.size, status="used",
                      pid=b.pid, requested_size=b.requested_size)
        new_blocks.append(new_b)
        pos += b.size

    if total_free > 0:
        new_blocks.append(Block(start=pos, size=total_free, status="free"))

    state.blocks = new_blocks
    _log(state, "COMPACT", pid=None, strategy="none")

    return {
        "before": [b.to_dict() for b in before],
        "after":  [b.to_dict() for b in new_blocks],
    }


# ─────────────────────────────────────────────
# Event logging
# ─────────────────────────────────────────────

def _log(state: SimState, event_type: str, *,
         pid=None, strategy=None, start=None, size=None, reason=None):
    state.event_log.append({
        "tick":     state.tick,
        "type":     event_type,
        "pid":      pid      if pid      is not None else "—",
        "strategy": strategy if strategy is not None else "none",
        "start":    start    if start    is not None else "—",
        "size":     size     if size     is not None else "—",
        "reason":   reason   if reason   is not None else "",
    })
    state.tick += 1