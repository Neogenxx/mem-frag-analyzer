"""
metrics.py — Fragmentation and memory metrics.
All formulas follow standard OS textbook definitions.
"""
from __future__ import annotations
from typing import List
from models import Block, SimState


def compute_metrics(state: SimState) -> dict:
    return metrics_from_blocks(state.blocks, state.total_size)


def metrics_from_blocks(blocks: List[Block], total_size: int) -> dict:
    free_blocks  = [b for b in blocks if b.status == "free"]
    used_blocks  = [b for b in blocks if b.status == "used"]

    total_free   = sum(b.size for b in free_blocks)
    total_used   = sum(b.size for b in used_blocks)
    largest_free = max((b.size for b in free_blocks), default=0)
    num_free     = len(free_blocks)
    num_used     = len(used_blocks)

    # Internal fragmentation: wasted space inside allocated blocks
    total_internal = sum(b.internal_frag for b in used_blocks)

    # External fragmentation = 1 - (largest_free / total_free)
    # 0.0 = all free is one contiguous block (best)
    # 1.0 = free space maximally scattered (worst)
    ext_frag = (1.0 - largest_free / total_free) if total_free > 0 else 0.0

    # Utilization = used / total
    utilization = total_used / total_size if total_size > 0 else 0.0

    return {
        "external_frag":    round(ext_frag, 4),
        "internal_frag":    total_internal,
        "free_space":       total_free,
        "used_space":       total_used,
        "largest_free":     largest_free,
        "num_free_blocks":  num_free,
        "num_used_blocks":  num_used,
        "utilization":      round(utilization, 4),
        "total_size":       total_size,
    }


def snapshot(state: SimState, label: str = "") -> dict:
    """Take a metrics snapshot and append to frag_history."""
    m = compute_metrics(state)
    entry = {
        "tick":          state.tick,
        "label":         label,
        "external_frag": m["external_frag"],
        "internal_frag": m["internal_frag"],
        "utilization":   m["utilization"],
        "free_space":    m["free_space"],
    }
    state.frag_history.append(entry)
    return entry