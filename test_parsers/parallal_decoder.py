import mmap
import struct
import time
from multiprocessing import Pool
from typing import Dict, List, Tuple
from bin_log_parser import BinLogParser
from helpers import find_valid_sync_positions, split_ranges

GLOBAL_FMT_DEFS: Dict[int, Dict] = {}
GLOBAL_FILE_PATH: str = ""


def _init_worker(fmt_defs: Dict[int, Dict], file_path: str):
    """Initializer for worker processes."""
    global GLOBAL_FMT_DEFS, GLOBAL_FILE_PATH
    GLOBAL_FILE_PATH = file_path
    GLOBAL_FMT_DEFS = {k: dict(v) for k, v in fmt_defs.items()}
    for f in GLOBAL_FMT_DEFS.values():
        if "struct_obj" not in f:
            f["struct_obj"] = struct.Struct(f["struct_fmt"])


def _decode_range(start: int, end: int, round_floats: bool) -> Dict:
    """Decode a specific file range."""
    with open(GLOBAL_FILE_PATH, "rb") as file:
        mapped = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
        parser = BinLogParser(mapped, format_definitions=GLOBAL_FMT_DEFS, round_floats=round_floats)

        message_count = 0
        samples: List[Dict] = []

        for msg in parser.decode_message_range(start, end, as_tuples=False):
            if msg["message_type"] == "FMT":
                continue
            message_count += 1
            if len(samples) < 3:
                samples.append(msg)

        mapped.close()
    return {"count": message_count, "sample": samples}


class ParallelBinDecoder:
    """Parallel decoder that splits a BIN log file between multiple workers."""

    def __init__(self, file_path: str, num_workers: int = 4, round_floats: bool = True):
        self.file_path = file_path
        self.num_workers = num_workers
        self.round_floats = round_floats

    def run(self):
        start_time = time.perf_counter()
        with open(self.file_path, "rb") as file:
            mapped = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
            parser = BinLogParser(mapped)
            parser.preload_fmt_messages()
            fmt_defs = {k: {kk: vv for kk, vv in v.items() if kk != "struct_obj"} for k, v in parser.format_definitions.items()}
            file_size = mapped.size()

            sync_positions = find_valid_sync_positions(mapped, parser.format_definitions)
            print(f"Found {len(sync_positions):,} valid sync markers.")
            ranges = split_ranges(sync_positions, self.num_workers, file_size)
            mapped.close()

        with Pool(self.num_workers, initializer=_init_worker, initargs=(fmt_defs, self.file_path)) as pool:
            results = pool.starmap(_decode_range, [(start, end, self.round_floats) for start, end in ranges])

        total_messages = sum(r["count"] for r in results)
        elapsed = time.perf_counter() - start_time
        print(f"\n✅ Decoded {total_messages:,} messages in {elapsed:.2f}s using {self.num_workers} workers.\n")

        for i, r in enumerate(results):
            print(f"[Worker {i}] Sample messages:")
            for msg in r["sample"]:
                print(f"  {msg['message_type']}: {msg}")
        return total_messages



if __name__ == "__main__":
    log_file = "log_file_test_01.bin"
    decoder = ParallelBinDecoder(log_file, num_workers=8, round_floats=True)
    decoder.run()
