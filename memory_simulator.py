#!/usr/bin/env python3
"""
Memory Allocation & Fragmentation Analyzer - core simulator.

Provides contiguous allocation simulation with First/Best/Worst Fit,
deallocation, compaction, fragmentation metrics, and an event runner.
"""

from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from math import ceil
from typing import List, Optional, Dict, Any, Tuple


@dataclass
class Block:
    start: int
    size: int
    pid: Optional[str] = None
    requested: Optional[int] = None

    def is_free(self) -> bool:
        return self.pid is None

    def __repr__(self) -> str:
        return f"Block(start={self.start}, size={self.size}, pid={self.pid}, req={self.requested})"


class MemorySimulator:
    def __init__(self, total_size: int, allocation_unit: int = 1):
        self.total_size = int(total_size)
        self.allocation_unit = max(1, int(allocation_unit))
        self.reset()

    def reset(self) -> None:
        # single free block at start
        self.blocks: List[Block] = [Block(0, self.total_size)]
        self.time = 0

    def snapshot(self) -> List[Block]:
        return deepcopy(self.blocks)

    def _alloc_size(self, requested: int) -> int:
        return int(ceil(requested / self.allocation_unit) * self.allocation_unit)

    def _merge_free_neighbors(self) -> None:
        merged: List[Block] = []
        for b in self.blocks:
            if merged and merged[-1].is_free() and b.is_free():
                merged[-1].size += b.size
            else:
                merged.append(deepcopy(b))
        # recompute starts
        start = 0
        for b in merged:
            b.start = start
            start += b.size
        self.blocks = merged

    def _find_candidate_indices(self, requested: int, strategy: str, blocks: Optional[List[Block]] = None) -> List[int]:
        if blocks is None:
            blocks = self.blocks
        alloc_size = self._alloc_size(requested)
        candidates = [(i, b.size) for i, b in enumerate(blocks) if b.is_free() and b.size >= alloc_size]
        if not candidates:
            return []
        if strategy == 'first':
            return [candidates[0][0]]
        elif strategy == 'best':
            candidates.sort(key=lambda x: x[1])
            return [i for i, _ in candidates]
        elif strategy == 'worst':
            candidates.sort(key=lambda x: x[1], reverse=True)
            return [i for i, _ in candidates]
        else:
            raise ValueError('unknown strategy')

    def _split_and_allocate(self, blocks: List[Block], idx: int, pid: str, requested: int) -> None:
        b = blocks[idx]
        alloc_size = self._alloc_size(requested)
        allocated = Block(b.start, alloc_size, pid=pid, requested=requested)
        remaining = b.size - alloc_size
        if remaining > 0:
            rem = Block(b.start + alloc_size, remaining)
            blocks[idx] = allocated
            blocks.insert(idx + 1, rem)
        else:
            blocks[idx] = allocated

    def allocate(self, pid: str, requested: int, strategy: str = 'first') -> bool:
        candidates = self._find_candidate_indices(requested, strategy)
        if not candidates:
            return False
        idx = candidates[0]
        self._split_and_allocate(self.blocks, idx, pid, requested)
        return True

    def free(self, pid: str) -> bool:
        found = False
        for i, b in enumerate(self.blocks):
            if not b.is_free() and b.pid == pid:
                self.blocks[i] = Block(b.start, b.size)
                found = True
        if found:
            self._merge_free_neighbors()
        return found

    def compact(self) -> None:
        new_blocks: List[Block] = []
        next_start = 0
        for b in self.blocks:
            if not b.is_free():
                nb = deepcopy(b)
                nb.start = next_start
                new_blocks.append(nb)
                next_start += nb.size
        free_size = self.total_size - next_start
        if free_size > 0:
            new_blocks.append(Block(next_start, free_size))
        self.blocks = new_blocks

    def fragmentation(self) -> Dict[str, int]:
        total_internal = 0
        total_free = 0
        largest_free = 0
        for b in self.blocks:
            if b.is_free():
                total_free += b.size
                if b.size > largest_free:
                    largest_free = b.size
            else:
                total_internal += (b.size - (b.requested if b.requested else b.size))
        return {
            'total_internal': total_internal,
            'total_free': total_free,
            'largest_free': largest_free,
            'external_excl_largest': total_free - largest_free,
        }

    def status_table(self) -> str:
        hdr = f"{'#':<3} {'start':<6} {'size':<6} {'status':<12} {'requested':<10} {'int_frag':<9}\n"
        sep = '-' * (len(hdr) - 1) + '\n'
        rows = [hdr, sep]
        for i, b in enumerate(self.blocks):
            status = 'Free' if b.is_free() else f"PID:{b.pid}"
            req = '-' if b.requested is None else str(b.requested)
            intf = '-' if b.requested is None else str(b.size - b.requested)
            rows.append(f"{i:<3} {b.start:<6} {b.size:<6} {status:<12} {req:<10} {intf:<9}\n")
        return ''.join(rows)

    def run_events(self, events: List[Dict[str, Any]], strategy: str = 'first', verbose: bool = False) -> Dict[str, Any]:
        """
        Run a sequence of events (alloc/free/compact) on the simulator.
        Returns dict with 'blocks', 'fragmentation', and 'results' (per event).
        """
        results = []
        for ev in events:
            op = ev.get('op')
            if op == 'alloc':
                pid = ev['pid']
                size = int(ev['size'])
                ok = self.allocate(pid, size, strategy)
                results.append({'event': ev, 'result': ok})
                if verbose:
                    print(f"alloc {pid} size={size} -> {'OK' if ok else 'FAIL'}")
            elif op == 'free':
                pid = ev['pid']
                ok = self.free(pid)
                results.append({'event': ev, 'result': ok})
                if verbose:
                    print(f"free {pid} -> {'OK' if ok else 'NOT FOUND'}")
            elif op == 'compact':
                self.compact()
                results.append({'event': ev, 'result': True})
                if verbose:
                    print("compacted memory")
            else:
                raise ValueError(f"unknown event op: {op}")
        return {
            'blocks': self.snapshot(),
            'fragmentation': self.fragmentation(),
            'results': results,
        }


# If run as script, demo simple scenario
if __name__ == "__main__":
    sim = MemorySimulator(1000, allocation_unit=1)
    events = [
        {"op": "alloc", "pid": "P1", "size": 212},
        {"op": "alloc", "pid": "P2", "size": 417},
        {"op": "alloc", "pid": "P3", "size": 112},
        {"op": "free",  "pid": "P2"},
        {"op": "alloc", "pid": "P4", "size": 85},
        {"op": "compact"},
    ]
    res = sim.run_events(events, strategy='first', verbose=True)
    print(sim.status_table())
    print("Fragmentation:", res['fragmentation'])
