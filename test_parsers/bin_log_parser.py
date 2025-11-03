import re
import struct
import mmap
import time
from typing import Dict, List, Optional, Tuple, Union

SYNC_MARKER = b"\xa3\x95"
FMT_TYPE_ID = 0x80
FMT_MESSAGE_LENGTH = 89

SCALE_FACTORS = {"c": 0.01, "C": 0.01, "e": 0.01, "E": 0.01, "L": 1e-7}


class BinLogParser:
    def __init__(
        self,
        mapped_flight_log: mmap.mmap,
        format_definitions: Optional[Dict[int, Dict]] = None,
        round_floats: bool = False,
    ):
        self.mapped_flight_log = mapped_flight_log
        self.format_definitions = format_definitions or {}
        self.round_floats = round_floats

        self._fields_to_round = {
            "Lat",
            "Lng",
            "Alt",
            "AltMSL",
            "AltRel",
            "BarAlt",
            "Vel",
            "Spd",
            "VN",
            "VE",
            "VD",
            "Roll",
            "Pitch",
            "Yaw",
        }

    # ---------------------------------------------------------------------
    # FMT scanning
    # ---------------------------------------------------------------------
    def preload_fmt_messages(self) -> int:
        """Scan the file for FMT message definitions and build format_definitions."""
        file_size = self.mapped_flight_log.size()
        print(f"[DEBUG] Scanning FMT messages in file of {file_size:,} bytes...")

        fmt_count = 0
        for offset in self._find_fmt_offsets():
            if self._parse_fmt_message(offset):
                fmt_count += 1

        self._build_struct_objects()
        print(f"[DEBUG] Total FMT definitions found: {fmt_count}")
        return fmt_count

    def _find_fmt_offsets(self):
        """Find all byte offsets where FMT messages (A3 95 80) appear."""
        position = 0
        file_size = self.mapped_flight_log.size()
        while position < file_size:
            next_fmt_offset = self.mapped_flight_log.find(b"\xa3\x95\x80", position)
            if next_fmt_offset == -1:
                break
            yield next_fmt_offset
            position = next_fmt_offset + FMT_MESSAGE_LENGTH

    # ---------------------------------------------------------------------
    # Message decoding
    # ---------------------------------------------------------------------
    def decode_message_range(
        self,
        start_offset: int,
        end_offset: Optional[int] = None,
        as_tuples: bool = False,
        message_filter: Optional[set] = None,
    ):
        """Decode all log messages within the specified byte range."""
        end_offset = end_offset or self.mapped_flight_log.size()
        position = start_offset
        unpack_cache = {}

        total_messages = 0
        start_time = time.perf_counter()

        while True:
            offset = self._find_next_message(self.mapped_flight_log, position, end_offset)
            if offset is None:
                break
            position = offset

            msg_id = self.mapped_flight_log[position + 2]
            if msg_id == FMT_TYPE_ID:
                position += FMT_MESSAGE_LENGTH
                continue

            fmt = self.format_definitions.get(msg_id)
            if not fmt or "struct_obj" not in fmt:
                position += 1
                continue

            if message_filter and fmt["name"] not in message_filter:
                position += fmt["message_length"]
                continue

            result = self._decode_single_message(fmt, position, end_offset, as_tuples, unpack_cache)
            if result is not None:
                yield result
                total_messages += 1

            position += fmt["message_length"]

        total_time = time.perf_counter() - start_time
        print(f"[DEBUG] Decoded {total_messages:,} messages in {total_time:.2f}s")

    def _decode_single_message(
        self,
        fmt: dict,
        position: int,
        end_offset: int,
        as_tuples: bool,
        unpack_cache: dict,
    ) -> Optional[Union[Tuple, Dict]]:
        """Decode a single message from the log."""
        payload_start = position + 3
        payload_end = payload_start + fmt["struct_size"]
        if payload_end > end_offset:
            return None

        try:
            values = self._unpack_values(fmt, payload_start, unpack_cache)
            scaled_values = self._apply_scaling(values, fmt["ardu_format"])
            return self._build_message(fmt, scaled_values, as_tuples)
        except struct.error:
            return None

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _find_next_message(self, mapped_log: mmap.mmap, position: int, end_offset: int) -> Optional[int]:
        """Locate the next synchronization marker in the file."""
        next_sync = mapped_log.find(SYNC_MARKER, position, end_offset)
        if next_sync == -1 or next_sync + 3 >= end_offset:
            return None
        return next_sync

    def _unpack_values(self, fmt: dict, payload_start: int, unpack_cache: dict) -> List:
        """Unpack binary payload into values using a cached struct."""
        msg_id = fmt["id"]
        if msg_id not in unpack_cache:
            unpack_cache[msg_id] = fmt["struct_obj"].unpack_from
        return list(unpack_cache[msg_id](self.mapped_flight_log, payload_start))

    def _apply_scaling(self, values: List, ardu_format: str) -> List:
        """Apply numeric scaling according to ArduPilot format specifiers."""
        return [
            v * SCALE_FACTORS[c] if c in SCALE_FACTORS and isinstance(v, (int, float)) else v
            for v, c in zip(values, ardu_format)
        ]

    def _build_message(self, fmt: dict, values: List, as_tuples: bool) -> Union[Tuple, Dict]:
        """Construct a decoded message as dict or tuple."""
        if as_tuples:
            return (fmt["name"], *values)

        message = dict(zip(fmt["field_names"], values))
        message["message_type"] = fmt["name"]

        # Decode bytes to text if possible
        for key, val in list(message.items()):
            if isinstance(val, (bytes, bytearray)):
                try:
                    message[key] = val.decode("ascii", "ignore").strip("\x00")
                except Exception:
                    pass

        if self.round_floats:
            for field in self._fields_to_round:
                if field in message and isinstance(message[field], float):
                    message[field] = round(message[field], 3)

        return message

    # ---------------------------------------------------------------------
    # FMT creation
    # ---------------------------------------------------------------------
    def _parse_fmt_message(self, offset: int) -> bool:
        """Parse one FMT message and store its definition."""
        try:
            m = self.mapped_flight_log
            msg_type = m[offset + 3]
            msg_name = m[offset + 5 : offset + 9].decode("ascii", "ignore").strip("\x00")
            if not re.match(r"^[A-Za-z0-9]+$", msg_name):
                return False

            ardu_format = m[offset + 9 : offset + 25].decode("ascii", "ignore").strip("\x00")
            field_names = self._extract_field_names(m[offset + 25 : offset + 89])
            struct_fmt = self._convert_to_struct_format(ardu_format)

            self.format_definitions[msg_type] = {
                "id": msg_type,
                "name": msg_name,
                "ardu_format": ardu_format,
                "field_names": field_names,
                "struct_fmt": struct_fmt,
                "struct_size": struct.calcsize(struct_fmt),
                "message_length": m[offset + 4],
            }
            print(f"[FMT #{len(self.format_definitions):03}] {msg_name} ({msg_type}) Fields={len(field_names)}")
            return True
        except Exception as err:
            print(f"[WARN] Bad FMT at {offset}: {err}")
            return False

    def _extract_field_names(self, raw_bytes: bytes) -> List[str]:
        """Extract field names from FMT raw data."""
        text = raw_bytes.decode("ascii", "ignore")
        cleaned = re.split(r"\x00{2,}", text)[0].strip("\x00").replace(" ", "")
        return [n for n in cleaned.split(",") if n]

    def _convert_to_struct_format(self, ardu_format: str) -> str:
        """Convert ArduPilot format string to Python struct format."""
        mapping = {
            "a": "32h",
            "b": "b", "B": "B",
            "h": "h", "H": "H",
            "i": "i", "I": "I",
            "q": "q", "Q": "Q",
            "f": "f", "d": "d",
            "n": "4s", "N": "16s", "Z": "64s",
            "c": "h",  # use short for scaled values (GPS)
            "C": "H",
            "e": "i", "E": "I",
            "L": "i",
            "M": "B",
        }
        return "<" + "".join(mapping.get(ch, "") for ch in ardu_format)

    def _build_struct_objects(self):
        """Prebuild struct objects for faster decoding."""
        for fmt in self.format_definitions.values():
            fmt["struct_obj"] = struct.Struct(fmt["struct_fmt"])
