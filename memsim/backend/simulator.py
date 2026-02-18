"""
Contiguous Memory Allocation Simulator
Supports First Fit, Best Fit, Worst Fit, Deallocation, and Compaction
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple
import math


@dataclass
class MemoryBlock:
    start: int
    size: int
    pid: Optional[str] = None      # None = free block
    logical_size: Optional[int] = None  # original request size

    @property
    def end(self):
        return self.start + self.size

    @property
    def is_free(self):
        return self.pid is None

    @property
    def internal_fragmentation(self):
        if self.pid is not None and self.logical_size is not None:
            return self.size - self.logical_size
        return 0

    def to_dict(self):
        return {
            "start": self.start,
            "end": self.end,
            "size": self.size,
            "pid": self.pid,
            "logical_size": self.logical_size,
            "is_free": self.is_free,
            "internal_fragmentation": self.internal_fragmentation,
        }


@dataclass
class AllocationResult:
    success: bool
    message: str
    block: Optional[MemoryBlock] = None
    strategy: str = ""
    logical_size: int = 0
    physical_size: int = 0
    wasted: int = 0

    def to_dict(self):
        return {
            "success": self.success,
            "message": self.message,
            "block": self.block.to_dict() if self.block else None,
            "strategy": self.strategy,
            "logical_size": self.logical_size,
            "physical_size": self.physical_size,
            "wasted": self.wasted,
        }


@dataclass
class FragmentationMetrics:
    total_memory: int
    total_allocated: int
    total_free: int
    internal_fragmentation: int
    external_fragmentation: int
    largest_free_block: int
    num_free_blocks: int
    num_allocated_blocks: int
    utilization_pct: float

    def to_dict(self):
        return asdict(self)


class MemorySimulator:
    def __init__(self, total_size: int = 1024, allocation_unit: int = 32):
        self.total_size = total_size
        self.allocation_unit = allocation_unit
        self.blocks: List[MemoryBlock] = [MemoryBlock(start=0, size=total_size)]
        self.event_log: List[dict] = []
        self._log_event("INIT", f"Memory initialized: {total_size} KB, unit={allocation_unit} KB")

    def _log_event(self, action: str, message: str, details: dict = None):
        entry = {
            "action": action,
            "message": message,
            "details": details or {},
            "snapshot": [b.to_dict() for b in self.blocks],
            "metrics": self.get_metrics().to_dict(),
        }
        self.event_log.append(entry)

    def _round_up(self, size: int) -> int:
        """Round logical size up to nearest allocation unit."""
        units = math.ceil(size / self.allocation_unit)
        return units * self.allocation_unit

    def _merge_free_blocks(self):
        """Coalesce adjacent free blocks."""
        merged = []
        for block in self.blocks:
            if merged and merged[-1].is_free and block.is_free:
                merged[-1].size += block.size
            else:
                merged.append(block)
        self.blocks = merged

    def _split_block(self, block_idx: int, physical_size: int, pid: str, logical_size: int) -> MemoryBlock:
        """Split a free block into allocated + remaining free."""
        original = self.blocks[block_idx]
        allocated = MemoryBlock(
            start=original.start,
            size=physical_size,
            pid=pid,
            logical_size=logical_size
        )
        remainder_size = original.size - physical_size
        new_blocks = [allocated]
        if remainder_size > 0:
            new_blocks.append(MemoryBlock(start=original.start + physical_size, size=remainder_size))
        self.blocks = self.blocks[:block_idx] + new_blocks + self.blocks[block_idx + 1:]
        return allocated

    def allocate_first_fit(self, pid: str, logical_size: int) -> AllocationResult:
        physical_size = self._round_up(logical_size)
        for i, block in enumerate(self.blocks):
            if block.is_free and block.size >= physical_size:
                allocated = self._split_block(i, physical_size, pid, logical_size)
                result = AllocationResult(
                    success=True,
                    message=f"First Fit: Allocated {physical_size} KB at {allocated.start} KB for PID {pid}",
                    block=allocated,
                    strategy="first_fit",
                    logical_size=logical_size,
                    physical_size=physical_size,
                    wasted=physical_size - logical_size,
                )
                self._log_event("ALLOC", result.message, result.to_dict())
                return result
        result = AllocationResult(
            success=False,
            message=f"First Fit: No block large enough for {physical_size} KB (PID {pid})",
            strategy="first_fit",
            logical_size=logical_size,
            physical_size=physical_size,
        )
        self._log_event("ALLOC_FAIL", result.message)
        return result

    def allocate_best_fit(self, pid: str, logical_size: int) -> AllocationResult:
        physical_size = self._round_up(logical_size)
        best_idx = None
        best_size = float("inf")
        for i, block in enumerate(self.blocks):
            if block.is_free and block.size >= physical_size:
                if block.size < best_size:
                    best_size = block.size
                    best_idx = i
        if best_idx is not None:
            allocated = self._split_block(best_idx, physical_size, pid, logical_size)
            result = AllocationResult(
                success=True,
                message=f"Best Fit: Allocated {physical_size} KB at {allocated.start} KB for PID {pid}",
                block=allocated,
                strategy="best_fit",
                logical_size=logical_size,
                physical_size=physical_size,
                wasted=physical_size - logical_size,
            )
            self._log_event("ALLOC", result.message, result.to_dict())
            return result
        result = AllocationResult(
            success=False,
            message=f"Best Fit: No block large enough for {physical_size} KB (PID {pid})",
            strategy="best_fit",
            logical_size=logical_size,
            physical_size=physical_size,
        )
        self._log_event("ALLOC_FAIL", result.message)
        return result

    def allocate_worst_fit(self, pid: str, logical_size: int) -> AllocationResult:
        physical_size = self._round_up(logical_size)
        worst_idx = None
        worst_size = -1
        for i, block in enumerate(self.blocks):
            if block.is_free and block.size >= physical_size:
                if block.size > worst_size:
                    worst_size = block.size
                    worst_idx = i
        if worst_idx is not None:
            allocated = self._split_block(worst_idx, physical_size, pid, logical_size)
            result = AllocationResult(
                success=True,
                message=f"Worst Fit: Allocated {physical_size} KB at {allocated.start} KB for PID {pid}",
                block=allocated,
                strategy="worst_fit",
                logical_size=logical_size,
                physical_size=physical_size,
                wasted=physical_size - logical_size,
            )
            self._log_event("ALLOC", result.message, result.to_dict())
            return result
        result = AllocationResult(
            success=False,
            message=f"Worst Fit: No block large enough for {physical_size} KB (PID {pid})",
            strategy="worst_fit",
            logical_size=logical_size,
            physical_size=physical_size,
        )
        self._log_event("ALLOC_FAIL", result.message)
        return result

    def free(self, pid: str) -> Tuple[bool, str]:
        freed = False
        for block in self.blocks:
            if block.pid == pid:
                block.pid = None
                block.logical_size = None
                freed = True
        if freed:
            self._merge_free_blocks()
            msg = f"Freed memory for PID {pid}"
            self._log_event("FREE", msg)
            return True, msg
        msg = f"PID {pid} not found in memory"
        self._log_event("FREE_FAIL", msg)
        return False, msg

    def compact(self) -> str:
        """Move all allocated blocks to the front, merging free space at end."""
        allocated = [b for b in self.blocks if not b.is_free]
        total_free = sum(b.size for b in self.blocks if b.is_free)
        cursor = 0
        new_blocks = []
        for block in allocated:
            new_blocks.append(MemoryBlock(
                start=cursor,
                size=block.size,
                pid=block.pid,
                logical_size=block.logical_size,
            ))
            cursor += block.size
        if total_free > 0:
            new_blocks.append(MemoryBlock(start=cursor, size=total_free))
        self.blocks = new_blocks
        msg = f"Compacted memory: {total_free} KB freed at end"
        self._log_event("COMPACT", msg)
        return msg

    def get_metrics(self) -> FragmentationMetrics:
        total_allocated = sum(b.size for b in self.blocks if not b.is_free)
        total_free = sum(b.size for b in self.blocks if b.is_free)
        internal_frag = sum(b.internal_fragmentation for b in self.blocks)
        free_blocks = [b for b in self.blocks if b.is_free]
        largest_free = max((b.size for b in free_blocks), default=0)
        # External fragmentation = total free space that can't be used as one block
        external_frag = total_free - largest_free if len(free_blocks) > 1 else 0
        utilization = (total_allocated / self.total_size * 100) if self.total_size > 0 else 0
        return FragmentationMetrics(
            total_memory=self.total_size,
            total_allocated=total_allocated,
            total_free=total_free,
            internal_fragmentation=internal_frag,
            external_fragmentation=external_frag,
            largest_free_block=largest_free,
            num_free_blocks=len(free_blocks),
            num_allocated_blocks=len([b for b in self.blocks if not b.is_free]),
            utilization_pct=round(utilization, 2),
        )

    def get_state(self) -> dict:
        return {
            "total_size": self.total_size,
            "allocation_unit": self.allocation_unit,
            "blocks": [b.to_dict() for b in self.blocks],
            "metrics": self.get_metrics().to_dict(),
        }

    def reset(self, total_size: Optional[int] = None, allocation_unit: Optional[int] = None):
        if total_size:
            self.total_size = total_size
        if allocation_unit:
            self.allocation_unit = allocation_unit
        self.blocks = [MemoryBlock(start=0, size=self.total_size)]
        self.event_log = []
        self._log_event("RESET", f"Memory reset: {self.total_size} KB, unit={self.allocation_unit} KB")
