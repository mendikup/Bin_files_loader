import re
import struct
import mmap
import time
from typing import Dict, List, Optional, Tuple

SYNC_MARKER = b"\xA3\x95"
FMT_TYPE_ID = 0x80
FMT_MESSAGE_LENGTH = 89
SCALE_FACTORS = {"c": 0.01, "C": 0.01, "e": 0.01, "E": 0.01, "L": 1e-7}


class BinLogParser:
    """Parser for ArduPilot .BIN log files (clean + optional rounding)."""

    def __init__(
        self,
        mapped_file: mmap.mmap,
        format_definitions: Optional[Dict[int, Dict]] = None,
        round_floats: bool = False,
    ):
        """
        Args:
            mapped_file: memory-mapped BIN file.
            format_definitions: optional dict of FMT definitions.
            round_floats: if True, round selected float fields for readability.
        """
        self.mapped_file = mapped_file
        self.format_definitions = format_definitions or {}
        self.round_floats = round_floats

        # Fields that should be rounded if round_floats=True
        self._fields_to_round = {
            "Lat", "Lng", "Alt", "AltMSL", "AltRel", "BarAlt", "AltHome",
            "Vel", "Spd", "VN", "VE", "VD", "GS",
            "Roll", "Pitch", "Yaw",
            "AccX", "AccY", "AccZ", "GyroX", "GyroY", "GyroZ",
            "VibeX", "VibeY", "VibeZ",
        }

    # -----------------------------------------------------------
    def preload_fmt_messages(self) -> int:
        """Scan the file for all FMT message definitions."""
        file_size = self.mapped_file.size()
        print(f"[DEBUG] Scanning for FMT messages in file of {file_size:,} bytes...")

        fmt_found = 0
        # 🟢 חזרה למבנה המקורי שלך
        for offset in self._find_sync_positions():
            if not self._is_fmt_message(offset):
                continue
            if self._parse_fmt_message(offset):
                fmt_found += 1

        self._rebuild_struct_objects()
        print(f"[DEBUG] Total FMT definitions found: {fmt_found}")
        return fmt_found

    # -----------------------------------------------------------
    def decode_all_messages(
        self,
        start: int,
        end: Optional[int] = None,
        raw_tuples: bool = True
    ) -> Tuple[int, float, float, float, float]:
        """
        Decode all messages in a byte range.

        Args:
            start: byte offset to start decoding from.
            end: optional byte offset to stop.
            raw_tuples: if True, yield (msg_name, *values) tuples instead of dicts for performance.

        Returns:
            tuple: (total_msgs, time_unpack, time_scale, time_dict, total_time)
        """
        mapped = self.mapped_file
        end = end or mapped.size()
        position = start
        unpack_cache = {}

        total_msgs = 0
        time_unpack = 0.0
        time_scale = 0.0
        time_dict = 0.0
        t0_total = time.perf_counter()

        while True:
            next_sync = mapped.find(SYNC_MARKER, position, end)
            if next_sync == -1 or next_sync + 3 >= end:
                break
            position = next_sync

            message_id = mapped[position + 2]
            if message_id == FMT_TYPE_ID:
                position += FMT_MESSAGE_LENGTH
                continue

            fmt = self.format_definitions.get(message_id)
            if not fmt:
                position += 1
                continue

            struct_obj = fmt.get("struct_obj")
            if not struct_obj:
                position += 1
                continue

            payload_start = position + 3
            payload_end = payload_start + fmt["struct_size"]
            if payload_end > end:
                break

            try:
                if message_id not in unpack_cache:
                    unpack_cache[message_id] = struct_obj.unpack_from
                unpack_fn = unpack_cache[message_id]
                t_start = time.perf_counter()
                values = list(unpack_fn(mapped, payload_start))
                time_unpack += time.perf_counter() - t_start
            except struct.error:
                position += 1
                continue

            t_start = time.perf_counter()
            ardu_fmt = fmt["ardu_format"]
            values = [
                v * SCALE_FACTORS[c] if c in SCALE_FACTORS else v
                for v, c in zip(values, ardu_fmt)
            ]
            time_scale += time.perf_counter() - t_start

            t_start = time.perf_counter()
            if raw_tuples:
                result = (fmt["name"], *values)
            else:
                message = dict(zip(fmt["field_names"], values))
                message["mavpackettype"] = fmt["name"]
                if self.round_floats:
                    for field_name in self._fields_to_round:
                        if field_name in message and isinstance(message[field_name], float):
                            message[field_name] = round(message[field_name], 3)
                result = message
            time_dict += time.perf_counter() - t_start

            total_msgs += 1
            yield result

            position += fmt["message_length"]

        total_time = time.perf_counter() - t0_total
        return total_msgs, time_unpack, time_scale, time_dict, total_time

    # -----------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------
    def _find_sync_positions(self):
        """Yield all byte offsets where SYNC_MARKER appears (optimized version)."""
        mapped = self.mapped_file
        pos = 0
        file_size = mapped.size()

        # שימוש ב-mmap.find במקום מעבר על כל בית
        while pos < file_size:
            idx = mapped.find(SYNC_MARKER, pos)
            if idx == -1:
                break
            yield idx
            pos = idx + 8  # דילוג קטן קדימה, לא מפספס הודעות אמיתיות

    def _is_fmt_message(self, offset: int) -> bool:
        mapped = self.mapped_file
        return (
            mapped[offset:offset + 2] == SYNC_MARKER
            and mapped[offset + 2] == FMT_TYPE_ID
            and offset + FMT_MESSAGE_LENGTH <= mapped.size()
        )

    def _parse_fmt_message(self, offset: int) -> bool:
        try:
            mapped = self.mapped_file
            msg_type = mapped[offset + 3]
            name = mapped[offset + 5:offset + 9].decode("ascii", "ignore").strip("\x00")
            if not re.match(r"^[A-Za-z0-9]+$", name):
                return False

            ardu_fmt = mapped[offset + 9:offset + 25].decode("ascii", "ignore").strip("\x00")
            raw_fields = mapped[offset + 25:offset + 89]
            field_names = self._clean_field_names(raw_fields)
            python_fmt = self._build_struct_format(ardu_fmt)

            self.format_definitions[msg_type] = {
                "name": name,
                "ardu_format": ardu_fmt,
                "field_names": field_names,
                "struct_fmt": python_fmt,
                "struct_size": struct.calcsize(python_fmt),
                "message_length": mapped[offset + 4],
            }

            print(f"[FMT #{len(self.format_definitions):03}] {name} ({msg_type}) Fields={len(field_names)}")
            return True
        except Exception as err:
            print(f"[WARN] Bad FMT at {offset}: {err}")
            return False

    def _clean_field_names(self, raw_bytes: bytes) -> List[str]:
        text = raw_bytes.decode("ascii", "ignore")
        text = re.split(r"\x00{2,}", text)[0].strip("\x00").replace(" ", "")
        return [name for name in text.split(",") if name]

    def _build_struct_format(self, ardu_format: str) -> str:
        fmt_map = {
            "a": "32h", "b": "b", "B": "B", "h": "h", "H": "H", "i": "i", "I": "I",
            "q": "q", "Q": "Q", "f": "f", "d": "d", "n": "4s", "N": "16s", "Z": "64s",
            "c": "h", "C": "H", "e": "i", "E": "I", "L": "i", "M": "B",
        }
        return "<" + "".join(fmt_map.get(ch, "") for ch in ardu_format)

    def _rebuild_struct_objects(self):
        """Recreate struct.Struct objects (used in worker processes)."""
        for fmt in self.format_definitions.values():
            if "struct_obj" not in fmt and "struct_fmt" in fmt:
                fmt["struct_obj"] = struct.Struct(fmt["struct_fmt"])
