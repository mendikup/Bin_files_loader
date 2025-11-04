import os
import mmap
import struct
import time
from multiprocessing import Pool
from typing import Dict, List, Tuple, Any
import tempfile
import pickle


from bin_log_parser import BinLogParser
from helpers import find_valid_sync_positions, split_ranges

SHARED_FMT_DEFINITIONS: Dict[int, Dict[str, Any]] = {}
SHARED_FILE_PATH: str = ""


def _init_worker(fmt_definitions: Dict[int, Dict[str, Any]], file_path: str) -> None:
    """
    Initialize each worker process:
    - Copy file path and fmt_definitions.
    - Build struct objects locally (not passed between processes).
    """
    global SHARED_FMT_DEFINITIONS, SHARED_FILE_PATH
    SHARED_FILE_PATH = file_path
    SHARED_FMT_DEFINITIONS = {msg_id: dict(fmt_def) for msg_id, fmt_def in fmt_definitions.items()}

    # each worker builds its own struct objects
    for fmt_def in SHARED_FMT_DEFINITIONS.values():
        fmt_def["struct_obj"] = struct.Struct(fmt_def["struct_fmt"])


def _decode_file_segment(segment_start: int, segment_end: int, round_floats: bool) -> str:
    """Decode messages and dump to a temporary file (return file path)."""
    with open(SHARED_FILE_PATH, "rb") as file:
        mapped_log = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
        parser = BinLogParser(mapped_log, format_definitions=SHARED_FMT_DEFINITIONS, round_floats=round_floats)
        messages = [m for m in parser.parse_messages_in_range(segment_start, segment_end, as_tuples=False)
                    if m["message_type"] != "FMT"]
        mapped_log.close()

    temp_file = tempfile.mktemp(suffix=".pkl")
    with open(temp_file, "wb") as f:
        pickle.dump(messages, f, protocol=pickle.HIGHEST_PROTOCOL)
    return temp_file


class ParallelBinDecoder:
    """Split BIN log file between multiple workers for parallel decoding."""

    def __init__(self, file_path: str, num_workers: int = 4, round_floats: bool = True) -> None:
        self.file_path = file_path
        self.num_workers = num_workers
        self.round_floats = round_floats

    def run(self) -> List[Dict[str, Any]]:
        start_time = time.perf_counter()

        with open(self.file_path, "rb") as file:
            mapped = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
            parser = BinLogParser(mapped)
            parser.preload_fmt_messages()
            fmt_defs = parser.fmt_definitions
            file_size = mapped.size()

            sync_positions = find_valid_sync_positions(mapped, parser.fmt_definitions)
            ranges = split_ranges(sync_positions, self.num_workers, file_size)
            mapped.close()

        with Pool(self.num_workers, initializer=_init_worker, initargs=(fmt_defs, self.file_path)) as pool:
            temp_files = pool.starmap(_decode_file_segment, [(s, e, self.round_floats) for s, e in ranges])

        # Load and merge from temp files
        all_messages = []
        for temp_path in temp_files:
            with open(temp_path, "rb") as f:
                all_messages.extend(pickle.load(f))
            os.remove(temp_path)

        all_messages.sort(key=lambda m: m.get("TimeUS", 0))

        elapsed = time.perf_counter() - start_time
        print(f"✅ Decoded {len(all_messages):,} messages in {elapsed:.2f}s (merged from temp files).")
        for msg in all_messages[:500]:
            print(msg)
        return all_messages


if __name__ == "__main__":
    log_file = "log_file_test_01.bin"
    decoder = ParallelBinDecoder(log_file, num_workers=8, round_floats=True)
    decoder.run()
