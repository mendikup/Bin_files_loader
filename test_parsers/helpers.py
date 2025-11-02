"""Helper utilities for safe file splitting in parallel BIN decoding."""

import mmap
import time
from typing import List, Tuple

SYNC_MARKER = b"\xA3\x95"


def find_all_sync_positions(mapped_file: mmap.mmap) -> List[int]:
    """
    Find all synchronization marker positions in the file efficiently.

    Args:
        mapped_file: memory-mapped BIN file.

    Returns:
        A list of byte offsets where SYNC_MARKER (0xA3 0x95) appears.
    """
    start_time = time.perf_counter()
    positions: List[int] = []
    file_size = mapped_file.size()
    start_offset = 0

    # שימוש ב־mmap.find() במקום memoryview.find()
    while start_offset < file_size:
        index = mapped_file.find(SYNC_MARKER, start_offset)
        if index == -1:
            break
        positions.append(index)
        # דילוג קטן קדימה (אין סיכון לפספס הודעה אמיתית)
        start_offset = index + 8

    elapsed = time.perf_counter() - start_time
    print(f"⏱️  Scanned SYNC markers: found {len(positions):,} in {elapsed:.3f}s")
    return positions


def split_into_equal_ranges(sync_positions: List[int], num_workers: int) -> List[Tuple[int, int]]:
    """
    Split the sync marker positions into approximately equal ranges.

    Each range defines (start_offset, end_offset) boundaries for a worker.

    Args:
        sync_positions: All offsets of valid SYNC markers.
        num_workers: Number of worker processes desired.

    Returns:
        A list of (start, end) tuples. The last end may be None (till EOF).
    """
    if not sync_positions:
        return []

    total_syncs = len(sync_positions)
    split_indexes = [i * total_syncs // num_workers for i in range(num_workers + 1)]

    ranges: List[Tuple[int, int]] = []
    for start_index, end_index in zip(split_indexes[:-1], split_indexes[1:]):
        start_offset = sync_positions[start_index]
        end_offset = sync_positions[end_index] if end_index < total_syncs else None
        ranges.append((start_offset, end_offset))

    return ranges
