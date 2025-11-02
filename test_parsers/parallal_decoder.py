"""
Parallel BIN log decoder (FAST / SAFE) – cleaned version
---------------------------------------------------------
- SAFE mode is the default
- Uses shared memory for format definitions (Manager.dict)
- Each worker rebuilds struct_obj locally
- Full variable names for clarity (no single letters)
"""

import argparse
import mmap
import struct
import time
from multiprocessing import Pool, Manager
from typing import Dict, Tuple, List, Optional

from test_parsers.bin_log_parser import BinLogParser
from test_parsers.helpers import find_all_sync_positions, split_into_equal_ranges

# Globals shared between worker processes
GLOBAL_FORMAT_DEFINITIONS = None
GLOBAL_FILE_PATH: Optional[str] = None


def _init_worker(shared_format_definitions, file_path: str):
    """
    Initialize each worker with shared format definitions and file path.
    """
    global GLOBAL_FORMAT_DEFINITIONS, GLOBAL_FILE_PATH
    GLOBAL_FORMAT_DEFINITIONS = shared_format_definitions
    GLOBAL_FILE_PATH = file_path


def _decode_range_worker(worker_arguments: Tuple[int, int, bool, bool]) -> Dict[str, object]:
    """
    Worker function: makes a local copy of format definitions,
    rebuilds struct objects, and decodes the assigned byte range.
    """
    start_offset, end_offset, should_round_floats, return_tuples = worker_arguments

    # Make a local copy of the shared format definitions (avoid pickling)
    shared_definitions = GLOBAL_FORMAT_DEFINITIONS
    local_definitions: Dict[int, Dict] = {
        message_id: dict(definition)
        for message_id, definition in shared_definitions.items()
    }

    # Rebuild struct.Struct objects locally (not stored in Manager.dict)
    for format_definition in local_definitions.values():
        if "struct_fmt" in format_definition and "struct_obj" not in format_definition:
            format_definition["struct_obj"] = struct.Struct(format_definition["struct_fmt"])

    with open(GLOBAL_FILE_PATH, "rb") as log_file:
        mapped_log = mmap.mmap(log_file.fileno(), 0, access=mmap.ACCESS_READ)
        parser = BinLogParser(
            mapped_log,
            format_definitions=local_definitions,
            round_floats=should_round_floats,
        )

        message_count = 0
        worker_start_time = time.perf_counter()
        for _ in parser.decode_all_messages(
            start_offset, end_offset, raw_tuples=return_tuples
        ):
            message_count += 1
        worker_decode_time = time.perf_counter() - worker_start_time

    return {
        "range": (start_offset, end_offset),
        "count": message_count,
        "decode_time": worker_decode_time,
    }


def _compute_ranges(file_path: str, file_size: int, num_workers: int, safe_split: bool) -> List[Tuple[int, int]]:
    """
    Compute byte ranges for each worker (SAFE or FAST split mode).
    """
    with open(file_path, "rb") as log_file:
        mapped_log = mmap.mmap(log_file.fileno(), 0, access=mmap.ACCESS_READ)

        if safe_split:
            print("[DEBUG] Using safe split by SYNC markers...")
            sync_positions = find_all_sync_positions(mapped_log)
            if not sync_positions:
                print("[WARN] No SYNC markers found — falling back to fast split.")
            else:
                ranges = split_into_equal_ranges(sync_positions, num_workers)
                return [
                    (start_offset, end_offset or file_size)
                    for start_offset, end_offset in ranges
                ]

        print("[DEBUG] Using fast split by file size...")
        chunk_size = file_size // num_workers
        return [
            (
                worker_index * chunk_size,
                file_size if worker_index == num_workers - 1 else (worker_index + 1) * chunk_size,
            )
            for worker_index in range(num_workers)
        ]


def run_parallel_decoder(
    file_path: str,
    num_workers: int = 8,
    should_round_floats: bool = False,
    return_tuples: bool = True,
    safe_split: bool = True,  # SAFE is the default
) -> Tuple[int, float]:
    """
    Run parallel BIN log decoding using multiple worker processes.
    """
    print(f"\n🔹 Starting parallel decode ({num_workers} processes)...")
    total_start_time = time.perf_counter()

    # 1️⃣ Preload FMT definitions
    preload_start_time = time.perf_counter()
    with open(file_path, "rb") as log_file:
        mapped_log = mmap.mmap(log_file.fileno(), 0, access=mmap.ACCESS_READ)
        parser = BinLogParser(mapped_log, round_floats=should_round_floats)
        parser.preload_fmt_messages()
        file_size = mapped_log.size()
        format_definitions = dict(parser.format_definitions)  # copy before closing mmap
        mapped_log.close()  # 🧹 close mmap after use
    preload_duration = time.perf_counter() - preload_start_time
    print(f"⏱️  Preload FMTs: {preload_duration:.3f}s (file size: {file_size:,} bytes)")

    # 2️⃣ Compute split ranges
    compute_start_time = time.perf_counter()
    byte_ranges = _compute_ranges(file_path, file_size, num_workers, safe_split)
    compute_duration = time.perf_counter() - compute_start_time
    print(f"⏱️  Compute ranges: {compute_duration:.3f}s (mode: {'SAFE' if safe_split else 'FAST'}, chunks: {len(byte_ranges)})")

    # 3️⃣ Share FMT definitions safely
    share_start_time = time.perf_counter()
    with Manager() as manager:
        serializable_definitions = {
            message_id: {
                key: value for key, value in definition.items() if key != "struct_obj"
            }
            for message_id, definition in format_definitions.items()
        }
        shared_definitions = manager.dict(serializable_definitions)
        share_duration = time.perf_counter() - share_start_time
        print(f"⏱️  Share FMT defs (Manager.dict): {share_duration:.3f}s")

        # 4️⃣ Parallel decoding
        job_arguments = [
            (start_offset, end_offset, should_round_floats, return_tuples)
            for start_offset, end_offset in byte_ranges
        ]

        pool_start_time = time.perf_counter()
        with Pool(
            num_workers,
            initializer=_init_worker,
            initargs=(shared_definitions, file_path),
        ) as pool:
            results = pool.map(_decode_range_worker, job_arguments)
        pool_duration = time.perf_counter() - pool_start_time
        print(f"⏱️  Pool run (map): {pool_duration:.3f}s")

    # 5️⃣ Collect results
    total_messages = sum(worker_result["count"] for worker_result in results)
    total_duration = time.perf_counter() - total_start_time
    total_decode_time = sum(worker_result["decode_time"] for worker_result in results)
    average_worker_time = total_decode_time / num_workers if num_workers else 0.0
    fastest_worker = min(results, key=lambda r: r["decode_time"])
    slowest_worker = max(results, key=lambda r: r["decode_time"])

    print(f"\n✅ Done: decoded {total_messages:,} messages in {total_duration:.2f}s ({num_workers} procs)")
    print(f"⚙️  Avg speed: {total_messages / total_duration:,.0f} msg/s")
    print(f"📊 Workers decode time: total={total_decode_time:.3f}s | avg/worker={average_worker_time:.3f}s")
    print(f"   Fastest worker: {fastest_worker['decode_time']:.3f}s, Slowest worker: {slowest_worker['decode_time']:.3f}s")

    return total_messages, total_duration


def compare_safe_vs_fast(file_path: str, num_workers: int = 8):
    """
    Compare SAFE vs FAST split decoding performance and consistency.
    """
    print("\n📊 Comparing SAFE vs FAST split performance...\n")
    safe_messages, safe_time = run_parallel_decoder(file_path, num_workers, safe_split=True)
    fast_messages, fast_time = run_parallel_decoder(file_path, num_workers, safe_split=False)

    message_difference = fast_messages - safe_messages
    loss_percentage = (message_difference / safe_messages * 100) if safe_messages else 0
    speed_difference = ((safe_time - fast_time) / safe_time * 100) if safe_time else 0

    print("\n🧾 Comparison Summary:")
    print(f"   SAFE : {safe_messages:,} msgs in {safe_time:.2f}s")
    print(f"   FAST : {fast_messages:,} msgs in {fast_time:.2f}s")
    print(f"   ➤ Δ msgs : {message_difference:+,} ({loss_percentage:+.4f}%)")
    print(f"   ➤ Speed Δ: {speed_difference:+.2f}%\n")


DEFAULT_OUTPUT_MODE_TUPLES = False  # True = tuples (fast), False = dicts (full)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parallel BIN log decoder (SAFE default)")
    parser.add_argument("--file", help="Path to .BIN file")
    parser.add_argument("--procs", type=int, default=8, help="Number of worker processes")
    parser.add_argument("--round", action="store_true", help="Round float fields for readability")
    parser.add_argument("--safe", action="store_true", help="Use SAFE split (default)")
    parser.add_argument("--fast", action="store_true", help="Use FAST split instead of SAFE")
    parser.add_argument("--compare", action="store_true", help="Compare SAFE vs FAST decoding results")

    args, _ = parser.parse_known_args()
    file_path = args.file or "log_file_test_01.bin"
    num_workers = args.procs
    should_round_floats = args.round
    safe_split = not args.fast  # default SAFE unless explicitly --fast

    print(f"\n🚀 Running parallel decode on {file_path}")
    print(f"   Mode: {'SAFE' if safe_split else 'FAST'} | Workers: {num_workers}")
    print(f"   Output mode: {'TUPLES' if DEFAULT_OUTPUT_MODE_TUPLES else 'DICTS'}")

    if args.compare:
        compare_safe_vs_fast(file_path, num_workers)
    else:
        run_parallel_decoder(
            file_path=file_path,
            num_workers=num_workers,
            should_round_floats=should_round_floats,
            return_tuples=DEFAULT_OUTPUT_MODE_TUPLES,
            safe_split=safe_split,
        )