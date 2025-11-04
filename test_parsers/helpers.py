import mmap
from typing import Dict, List, Tuple

SYNC_MARKER = b"\xa3\x95"


def find_valid_sync_positions(mapped_log: mmap.mmap, fmt_defs: Dict[int, Dict]) -> List[int]:
    """Return offsets of valid sync markers where the message type is known."""
    file_size = mapped_log.size()
    pos = 0
    positions = []

    while True:
        pos = mapped_log.find(SYNC_MARKER, pos)
        if pos == -1 or pos + 3 >= file_size:
            break
        msg_id = mapped_log[pos + 2]
        fmt = fmt_defs.get(msg_id)
        if fmt:
            msg_len = fmt["message_length"]
            if pos + msg_len <= file_size:
                positions.append(pos)
        pos += 1
    return positions


def split_ranges(syncs: List[int], num_parts: int, file_size: int) -> List[Tuple[int, int]]:
    """Split the file into balanced non-overlapping ranges based on valid syncs."""
    if not syncs:
        return [(0, file_size)]

    num_parts = max(1, min(num_parts, len(syncs)))
    per_part = len(syncs) // num_parts
    remainder = len(syncs) % num_parts

    ranges = []
    index = 0
    for i in range(num_parts):
        take = per_part + (1 if i < remainder else 0)
        start = syncs[index]
        index2 = index + take
        end = file_size if index2 >= len(syncs) else syncs[index2]
        ranges.append((start, end))
        index = index2

    return ranges








