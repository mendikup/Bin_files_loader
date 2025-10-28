# bin_log_parser.py
# Simple, fast ArduPilot .BIN parser:
# - Pass 1 (parse): read FMTs, count only validated messages, skip fast by msg_len when known
# - Pass 2 (decode): decode regular messages using FMT; optional printing/debug and dict building

import struct
import re
import time
from typing import Dict, List, Tuple, Optional


class BinLogParser:
    # ---- Binary framing ----
    SYNC_BYTES = b"\xA3\x95"
    FMT_TYPE_ID = 0x80
    FMT_MESSAGE_LENGTH = 89

    # ---- ArduPilot format → Python struct ----
    # Note: 'c','C','e','E','L' are scaled numeric types (scale applied after unpack)
    STRUCT_MAP: Dict[str, str] = {
        "a": "32h",
        "b": "b", "B": "B",
        "h": "h", "H": "H",
        "i": "i", "I": "I",
        "q": "q", "Q": "Q",
        "f": "f", "d": "d",
        "n": "4s", "N": "16s", "Z": "64s",
        "c": "h", "C": "H",   # ×100
        "e": "i", "E": "I",   # ×100
        "L": "i", "M": "B",   # L = lat/lon 1e-7 deg, M = flight mode
    }


    SCALE_MAP: Dict[str, float] = {
        "c": 0.01,  # int16 / 100
        "C": 0.01,  # uint16 / 100
        "e": 0.01,  # int32 / 100
        "E": 0.01,  # uint32 / 100
        "L": 1e-7,  # lat/lon in degrees
    }

    # Fallback GPS field list if columns string is corrupted/short
    GPS_FALLBACK_FIELDS: List[str] = [
        "TimeUS", "I", "Status", "GMS", "GWk", "NSats",
        "HDop", "Lat", "Lng", "Alt", "Spd", "GCrs", "VZ", "Yaw"
    ]

    def __init__(self, file_path: str):
        self.file_path = file_path

        #   type_id -> (name, ardu_fmt, fields, msg_len)
        self.fmt_definitions: Dict[int, Tuple[str, str, List[str], int]] = {}

        # Debug/metrics for parse()
        self.parsed_suspected_syncs = 0
        self.parsed_validated_msgs = 0
        self.parsed_validated_fmt = 0
        self.parsed_validated_nonfmt = 0
        self.parsed_unknown_skips = 0

        # Debug/metrics for decode()
        self.decoded_messages = 0

    # -----------------------------
    # Helpers
    # -----------------------------
    @staticmethod
    def _clean_columns(columns_raw: bytes) -> List[str]:
        """Clean and split the 64-byte columns area into a list of field names."""
        s = columns_raw.decode("ascii", "ignore")
        # Cut at padding (double-null or more)
        s = re.split(r"\x00{2,}", s)[0]
        # Strip single nulls and spaces
        s = s.strip("\x00").replace(" ", "")
        # Split and drop empties
        fields = [c for c in s.split(",") if c]
        return fields

    @staticmethod
    def _build_struct_fmt(ardu_fmt: str) -> str:
        """Convert ArduPilot format string to Python struct format (little-endian)."""
        parts = []
        for ch in ardu_fmt:
            mapped = BinLogParser.STRUCT_MAP.get(ch, "")
            if not mapped:
                # Unknown char: ignore silently (or raise if you prefer strictness)
                continue
            parts.append(mapped)
        return "<" + "".join(parts)

    @staticmethod
    def _format_as_kv(name: str, fields: List[str], values: List[object]) -> str:
        """Create a Mavlink-like single-line string without building a dict."""
        parts = [f"{f} : {v}" for f, v in zip(fields, values)]
        return f"{name} {{{', '.join(parts)}}}"

    # -----------------------------
    # Pass 1: Parse FMTs + fast skipping
    # -----------------------------
    def parse(self, progress_every: int = 100_000, show_fmt: bool = False) -> None:
        """
        Read FMT messages and store structure definitions. For non-FMT messages
        whose length is already known (from a previous FMT), skip quickly by msg_len.
        Count ONLY validated messages (those we fully consume).
        """
        with open(self.file_path, "rb") as f:
            data = f.read()

        mv = memoryview(data)  # faster slicing without copies
        index = 0
        file_size = len(data)
        start = time.time()

        self.parsed_suspected_syncs = 0
        self.parsed_validated_msgs = 0
        self.parsed_validated_fmt = 0
        self.parsed_validated_nonfmt = 0
        self.parsed_unknown_skips = 0

        while index <= file_size - 3:
            # Look for sync bytes
            if mv[index:index + 2] != self.SYNC_BYTES:
                index += 1
                continue

            self.parsed_suspected_syncs += 1
            msg_type = mv[index + 2]

            # ----- FMT (fixed 89 bytes) -----
            if msg_type == self.FMT_TYPE_ID:
                if index + self.FMT_MESSAGE_LENGTH > file_size:
                    break  # truncated at EOF

                # Extract FMT payload
                type_id = mv[index + 3]
                msg_len = mv[index + 4]  # length of messages of THIS type (not FMT itself)

                name = bytes(mv[index + 5:index + 9]).decode("ascii", "ignore").strip("\x00")
                ardu_fmt = bytes(mv[index + 9:index + 25]).decode("ascii", "ignore").strip("\x00")

                columns_raw = bytes(mv[index + 25:index + 25 + 64])
                fields = self._clean_columns(columns_raw)

                # Fix GPS fields if corrupted/short
                if name == "GPS" and len(fields) < 10:
                    fields = self.GPS_FALLBACK_FIELDS[:]

                self.fmt_definitions[type_id] = (name, ardu_fmt, fields, msg_len)

                if show_fmt:
                    print(f"FMT {{type_id: {type_id}, name: {name}, len: {msg_len}, fmt: '{ardu_fmt}', fields: {fields}}}")

                # Consume full FMT message
                index += self.FMT_MESSAGE_LENGTH
                self.parsed_validated_msgs += 1
                self.parsed_validated_fmt += 1

                if self.parsed_validated_msgs % progress_every == 0:
                    print(
                        f"📊 Parsed {self.parsed_validated_msgs:,} messages... "
                        f"(FMT={self.parsed_validated_fmt:,}, Non-FMT={self.parsed_validated_nonfmt:,})",
                        flush=True,
                    )
                continue

            # ----- Non-FMT -----
            entry = self.fmt_definitions.get(msg_type)
            if entry:
                # We know this type's message length — skip fast
                _, _, _, msg_len = entry
                if 5 <= msg_len <= 255 and index + msg_len <= file_size:
                    index += msg_len
                    self.parsed_validated_msgs += 1
                    self.parsed_validated_nonfmt += 1

                    if self.parsed_validated_msgs % progress_every == 0:
                        print(
                            f"📊 Parsed {self.parsed_validated_msgs:,} messages... "
                            f"(FMT={self.parsed_validated_fmt:,}, Non-FMT={self.parsed_validated_nonfmt:,})",
                            flush=True,
                        )
                    continue

            # Unknown length yet (FMT not seen), or suspicious length → advance 1 byte
            index += 1
            self.parsed_unknown_skips += 1

        elapsed = time.time() - start
        print(f"✅ Finished FMT parsing in {elapsed:.2f}s")
        print(f"   • FMT definitions: {len(self.fmt_definitions)}")
        print(f"   • Suspected SYNCs: {self.parsed_suspected_syncs:,}")
        print(f"   • Validated msgs:  {self.parsed_validated_msgs:,} (FMT={self.parsed_validated_fmt:,}, Non-FMT={self.parsed_validated_nonfmt:,})")
        print(f"   • Unknown +1 skips:{self.parsed_unknown_skips:,}")

    # -----------------------------
    # Pass 2: Decode messages
    # -----------------------------
    def decode(
        self,
        verbose: bool = False,
        build_dicts: bool = False,
        progress_every: int = 100_000,
        limit: Optional[int] = None,
    ) -> None:
        """
        Decode all non-FMT messages using FMT definitions.
        - verbose=True: print each message in Mavlink-like single-line format (slow)
        - build_dicts=True: build Python dict for each message (slower, memory-heavy)
        - limit: stop after N decoded messages (helpful for testing)
        """
        with open(self.file_path, "rb") as f:
            data = f.read()

        mv = memoryview(data)
        index = 0
        file_size = len(data)
        start = time.time()

        self.decoded_messages = 0

        # Pre-cache struct formats and sizes per type for speed
        struct_cache: Dict[int, Tuple[str, int]] = {}
        for t_id, (_, ardu_fmt, _, _) in self.fmt_definitions.items():
            py_fmt = self._build_struct_fmt(ardu_fmt)
            struct_cache[t_id] = (py_fmt, struct.calcsize(py_fmt))

        while index <= file_size - 3:
            if mv[index:index + 2] != self.SYNC_BYTES:
                index += 1
                continue

            msg_type = mv[index + 2]
            if msg_type == self.FMT_TYPE_ID:
                # Skip FMT in decode pass
                index += self.FMT_MESSAGE_LENGTH
                continue

            entry = self.fmt_definitions.get(msg_type)
            if not entry:
                # Unknown type (FMT for it not yet seen) → shift by 1
                index += 1
                continue

            name, ardu_fmt, fields, msg_len = entry

            # We use msg_len (includes header) to advance; payload size is from struct
            py_fmt, payload_size = struct_cache[msg_type]
            payload_start = index + 3
            payload_end = payload_start + payload_size

            if payload_end > file_size or index + msg_len > file_size:
                # Truncated at EOF
                break

            # Unpack payload
            values = list(struct.unpack(py_fmt, mv[payload_start:payload_end]))

            # Apply scaling
            # Important: iterates by original ardu_fmt order
            for j, ch in enumerate(ardu_fmt):
                if j >= len(values):
                    break
                scale = self.SCALE_MAP.get(ch)
                if scale is not None:
                    values[j] = values[j] * scale

            # Output (optional, to keep it fast by default)
            if verbose:
                # Print without building dict
                print(self._format_as_kv(name, fields, values))

            if build_dicts:
                # If needed, build dict (slower)
                msg = dict(zip(fields, values))
                _ = msg  # place-holder if you want to collect/store later

            # Advance by the declared message length (fast, aligned)
            index += msg_len
            self.decoded_messages += 1

            if self.decoded_messages % progress_every == 0:
                print(f"📊 Decoded {self.decoded_messages:,} messages...", flush=True)

            if limit and self.decoded_messages >= limit:
                break

        elapsed = time.time() - start
        print(f"✅ Finished decoding in {elapsed:.2f}s")
        print(f"   • Decoded messages: {self.decoded_messages:,}")


# -----------------------------
# CLI usage example
# -----------------------------
if __name__ == "__main__":
    FILE_PATH = "log_file_test_01.bin"

    parser = BinLogParser(FILE_PATH)

    print("🔹 Extracting FMT definitions...")
    # show_fmt=False כדי לרוץ מהר; True יציג כל FMT שמצאנו
    parser.parse(progress_every=100_000, show_fmt=False)

    print("\n🔹 Decoding all messages according to FMT...\n")
    # verbose/build_dicts=False לשמירה על מהירות; אפשר להפעיל פיתוחית
    parser.decode(verbose=False, build_dicts=False, progress_every=100_000)
