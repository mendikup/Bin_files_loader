import os
import re
import struct
import mmap
import time
from typing import Dict, List, Iterator, Optional
from multiprocessing import Pool, get_context



LOG_FILE = "log_file_test_01.bin"
SYNC_MARKER = b"\xA3\x95"
FMT_TYPE_ID = 0x80
FMT_MESSAGE_LENGTH = 89

# Scale factors for specific ArduPilot field types
SCALE_FACTORS = {"c": 0.01,
                 "C": 0.01,
                 "e": 0.01,
                 "E": 0.01,
                 "L": 1e-7}



class BinLogParser:
    """
    Parses ArduPilot .BIN log files using memory mapping.
    Responsible for scanning FMT definitions and decoding messages.
    """

    def __init__(self, mapped_file: mmap.mmap, format_definitions: Optional[Dict[int, Dict]] = None):
        """Initialize the parser with a memory-mapped file and optional format definitions."""
        self.mapped_file = mapped_file
        self.format_definitions = format_definitions or {}


    def preload_fmt_messages(self) -> int:
        """
        Scan the file and load all valid FMT definitions.
        """
        print(f"[DEBUG] Scanning for FMT messages in file of {self.mapped_file.size():,} bytes...")

        fmt_found = 0
        for offset in self._find_sync_positions():
            if not self._is_fmt_message(offset):
                continue

            if self._parse_single_fmt(offset):
                fmt_found += 1

        self._rebuild_struct_objects()
        print(f"[DEBUG] Total FMT definitions found: {fmt_found}")
        return fmt_found

    def decode_all_messages(self, start: int, end: Optional[int] = None) -> Iterator[Dict[str, object]]:
        """
        Decode all valid messages (non-FMT) in the given range.
        """
        mapped = self.mapped_file
        end = end or mapped.size()
        position = start

        while position < end - 3:
            if mapped[position:position + 2] != SYNC_MARKER:
                position += 1
                continue

            msg_id = mapped[position + 2]
            if msg_id == FMT_TYPE_ID:
                position += FMT_MESSAGE_LENGTH
                continue

            fmt = self.format_definitions.get(msg_id)
            if not fmt:
                position += 1
                continue

            payload_start = position + 3
            payload_end = payload_start + fmt["struct_size"]
            if payload_end > end:
                break

            try:
                values = list(fmt["struct_obj"].unpack_from(mapped, payload_start))
            except struct.error:
                position += 1
                continue

            # Apply scale factors
            for i, char in enumerate(fmt["ardu_format"]):
                if char in SCALE_FACTORS and i < len(values):
                    values[i] *= SCALE_FACTORS[char]

            # Build message dictionary
            msg = {"mavpackettype": fmt["name"]}
            for i, field_name in enumerate(fmt["field_names"]):
                val = values[i] if i < len(values) else None
                if isinstance(val, (bytes, bytearray)):
                    val = val.decode("ascii", "ignore").rstrip("\x00") or None
                msg[field_name] = val

            yield msg
            position += fmt["message_length"]


    def _find_sync_positions(self) -> Iterator[int]:
        """Iterate over all sync marker positions in the mapped file."""
        mapped = self.mapped_file
        size = mapped.size()
        pos = 0
        while pos < size - 2:
            if mapped[pos:pos + 2] == SYNC_MARKER:
                yield pos
            pos += 1

    def _is_fmt_message(self, offset: int) -> bool:
        """Check if the given offset points to a valid FMT message."""
        mapped = self.mapped_file
        return (
            mapped[offset:offset + 2] == SYNC_MARKER
            and mapped[offset + 2] == FMT_TYPE_ID
            and offset + FMT_MESSAGE_LENGTH <= mapped.size()
        )

    def _parse_single_fmt(self, offset: int) -> bool:
        """Parse one FMT definition and add it to the definitions map."""
        mapped = self.mapped_file
        try:
            defined_msg_id = mapped[offset + 3]
            name = mapped[offset + 5:offset + 9].decode("ascii", "ignore").strip("\x00")

            # skip non-alphanumeric FMT names
            if not re.match(r"^[A-Za-z0-9]+$", name):
                return False

            ardu_fmt = mapped[offset + 9:offset + 25].decode("ascii", "ignore").strip("\x00")
            raw_fields = mapped[offset + 25:offset + 89]
            field_names = self._clean_field_names(raw_fields)
            python_fmt = self._build_python_adru_format(ardu_fmt)

            self.format_definitions[defined_msg_id] = {
                "name": name,
                "ardu_format": ardu_fmt,
                "field_names": field_names,
                "struct_fmt": python_fmt,
                "struct_size": struct.calcsize(python_fmt),
                "message_length": mapped[offset + 4],
            }

            print(
                f"[FMT #{len(self.format_definitions):03}] "
                f"Type={defined_msg_id:3} Name={name:6} "
                f"Fmt={ardu_fmt:20} Fields={len(field_names)}"
            )
            return True

        except Exception as e:
            print(f"[WARN] Bad FMT at {offset}: {e}")
            return False

    # --------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------
    def _clean_field_names(self, raw_bytes: bytes) -> List[str]:
        """Convert raw bytes of field names into a clean list."""
        text = raw_bytes.decode("ascii", "ignore")
        text = re.split(r"\x00{2,}", text)[0].strip("\x00").replace(" ", "")
        return [field for field in text.split(",") if field]

    def _build_python_adru_format(self, ardu_format: str) -> str:
        """Convert ArduPilot format string into Python struct format."""
        ARDUPILOT_TO_PYTHON_STRUCT_MAP = {
            "a": "32h", "b": "b", "B": "B", "h": "h", "H": "H",
            "i": "i", "I": "I", "q": "q", "Q": "Q", "f": "f", "d": "d",
            "n": "4s", "N": "16s", "Z": "64s", "c": "h", "C": "H",
            "e": "i", "E": "I", "L": "i", "M": "B",
        }
        return "<" + "".join(ARDUPILOT_TO_PYTHON_STRUCT_MAP.get(ch, "") for ch in ardu_format)

    def _rebuild_struct_objects(self) -> None:
        """Recreate struct.Struct objects for multiprocessing workers."""
        for fmt in self.format_definitions.values():
            if "struct_obj" not in fmt and "struct_fmt" in fmt:
                fmt["struct_obj"] = struct.Struct(fmt["struct_fmt"])




# ===============================
# Parallel decoding helpers
# ===============================
def find_all_sync_positions(mapped_file: mmap.mmap) -> List[int]:
    """Return all sync marker positions for splitting the file."""
    positions = []
    search_start = 0
    file_size = mapped_file.size()
    while True:
        pos = mapped_file.find(SYNC_MARKER, search_start)
        if pos == -1 or pos + 3 >= file_size:
            break
        positions.append(pos)
        search_start = pos + 1
    return positions


def split_into_equal_ranges(sync_positions: List[int], num_workers: int):
    """Split sync marker positions into approximately equal ranges."""
    if not sync_positions:
        return []
    total = len(sync_positions)
    indices = [i * total // num_workers for i in range(num_workers + 1)]
    return [(sync_positions[i], sync_positions[j] if j < total else None)
            for i, j in zip(indices[:-1], indices[1:])]


def worker_decode_range(args):
    """Worker process: count valid decoded messages in the given range."""
    file_path, start, end, fmt_defs = args
    with open(file_path, "rb") as f:
        mapped = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        parser = BinLogParser(mapped, fmt_defs.copy())
        parser._rebuild_struct_objects()   # ✅ add this line!

        count = 0
        for _ in parser.decode_all_messages(start, end):
            count += 1

        mapped.close()
    end_display = end if end is not None else "EOF"
    print(f"[PID={os.getpid()}] Done: {count:,} msgs from {start:,}-{end_display}")
    return count



# ===============================
# Main runner
# ===============================
def run_parallel_decoder():
    """Main entry point for parallel BIN log decoding."""
    if not os.path.exists(LOG_FILE):
        print(f"Error: file {LOG_FILE} not found!")
        return

    start_time = time.time()
    with open(LOG_FILE, "rb") as f:
        mapped = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        parser = BinLogParser(mapped)
        fmt_count = parser.preload_fmt_messages()
        formats = {k: v.copy() for k, v in parser.format_definitions.items()}
        for v in formats.values():
            v.pop("struct_obj", None)
        syncs = find_all_sync_positions(mapped)
        ranges = split_into_equal_ranges(syncs, num_workers=4)
        mapped.close()

    jobs = [(LOG_FILE, s, e, formats) for s, e in ranges]
    with get_context("spawn").Pool(4) as pool:
        results = pool.map(worker_decode_range, jobs)

    total_msgs = sum(results)
    elapsed = time.time() - start_time
    print(f"\nCustom parser: {total_msgs:,} msgs | {fmt_count} FMT | {elapsed:.2f}s")


# ===============================
# Run
# ===============================
if __name__ == "__main__":
    run_parallel_decoder()
