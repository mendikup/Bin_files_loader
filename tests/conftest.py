import json
import time
import struct
from collections import Counter
from typing import Dict, List, Tuple, Optional
import pandas as pd

# ✅ ייבוא לוגר אחיד לכל המערכת
from src.utils.logger import logger


class BinLogParser:
    """
    Parser for ArduPilot .BIN log files.

    Responsibilities:
    -----------------
    - Detect and decode FMT (format) messages
    - Extract metadata for all messages
    - Decode specific message types (e.g., GPS) into real numeric values
    - Export results to JSON, DataFrame, or Parquet
    """

    SYNC_BYTES = b"\xA3\x95"
    FMT_TYPE_ID = 0x80
    MAX_MESSAGES = 8_000_000
    MIN_VALID_FMT_LEN = 16
    EXPECTED_FMT_COUNT = 180

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
    def __init__(self, file_path: str):
        """Initialize a parser instance for a specific binary log file."""
        self.file_path = file_path
        self.fmt_definitions: Dict[int, Tuple[str, int, str]] = {}
        self.fmt_field_names: Dict[str, List[str]] = {}
        self.msg_statistics: Counter = Counter()
        self.messages_data: List[Dict] = []
        self.total_msgs = 0
        self.skipped_msgs = 0
        self.file_size = 0
        self.parse_time: Optional[float] = None
        self.json_write_time: Optional[float] = None
        self.df_write_time: Optional[float] = None

    # ------------------------------------------------------------------
    # Public Interface
    # ------------------------------------------------------------------
    def parse(self, max_msgs: Optional[int] = None) -> None:
        """
        Parse the binary file, detecting FMT definitions and message metadata.
        """
        logger.info(f"Starting parse for file: {self.file_path}")
        start_time = time.perf_counter()
        max_msgs = max_msgs or self.MAX_MESSAGES

        try:
            with open(self.file_path, "rb") as f:
                data = f.read()
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"Error reading file: {e}")
            raise RuntimeError(f"Error reading file '{self.file_path}': {e}")

        self.file_size = len(data)
        index = 0
        self.fmt_definitions[self.FMT_TYPE_ID] = ("FMT", 89, "BBI4s16s64s")

        try:
            while True:
                sync_pos = data.find(self.SYNC_BYTES, index)
                if sync_pos == -1 or self.total_msgs >= max_msgs:
                    break
                if sync_pos + 4 >= self.file_size:
                    break

                msg_type = data[sync_pos + 2]

                if msg_type == self.FMT_TYPE_ID:
                    index = self._parse_fmt_message(data, sync_pos)
                elif msg_type in self.fmt_definitions:
                    index = self._parse_regular_message(data, sync_pos, msg_type)
                else:
                    self.msg_statistics[f"Unknown_{msg_type}"] += 1
                    self.total_msgs += 1
                    index = sync_pos + 1

        except Exception as e:
            logger.exception(f"Unexpected parsing error: {e}")
            raise

        self.parse_time = time.perf_counter() - start_time
        logger.info(
            f"Parsed {self.total_msgs:,} messages in {self.parse_time:.2f} seconds "
            f"({self.skipped_msgs:,} skipped)"
        )

    def to_json(self, output_path: str) -> Dict[str, float]:
        """Save parsed results to a JSON file."""
        if not self.messages_data:
            raise ValueError("No messages parsed. Run parse() first.")

        start = time.perf_counter()
        logger.info(f"Writing JSON output to {output_path}")

        data = {
            "file": self.file_path,
            "total_messages": self.total_msgs,
            "skipped_messages": self.skipped_msgs,
            "formats": {
                str(k): {
                    "name": v[0],
                    "length": v[1],
                    "format": v[2],
                    "fields": self.fmt_field_names.get(v[0], []),
                }
                for k, v in self.fmt_definitions.items()
            },
            "messages": self.messages_data,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.json_write_time = time.perf_counter() - start
        logger.info(f"JSON saved in {self.json_write_time:.2f} sec")
        return {"json_write_time_sec": self.json_write_time}

    def to_dataframe(self) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """Convert message metadata into a Pandas DataFrame."""
        if not self.messages_data:
            raise ValueError("No messages parsed. Run parse() first.")

        start = time.perf_counter()
        df = pd.DataFrame(self.messages_data)
        self.df_write_time = time.perf_counter() - start
        logger.debug(f"DataFrame created ({len(df)} rows)")
        return df, {"df_write_time_sec": self.df_write_time, "rows": len(df)}

    def decode_messages(
        self,
        df: pd.DataFrame,
        filter_name: str,
        output_columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Decode specific message types (e.g., GPS) from the BIN file.

        Automatically retrieves field names, validates structure length,
        and performs auto-conversion for GPS coordinates (Lat/Lon/Alt).
        """
        if not self.file_path:
            raise ValueError("No binary file path provided.")

        target_df = df[df["name"] == filter_name].copy()
        if target_df.empty:
            raise ValueError(f"No messages found with name '{filter_name}'.")

        fmt_entry = next(
            (fmt for fmt in self.fmt_definitions.values() if fmt[0] == filter_name), None
        )
        if not fmt_entry:
            raise ValueError(f"FMT definition for '{filter_name}' not found.")

        _, msg_len, ardu_fmt = fmt_entry
        field_names = (
            self.fmt_field_names.get(filter_name)
            or output_columns
            or [f"field_{i}" for i in range(len(ardu_fmt))]
        )

        struct_fmt = self._convert_fmt_to_struct(ardu_fmt)
        fmt_size = struct.calcsize(struct_fmt)

        decoded_rows = []
        with open(self.file_path, "rb") as f:
            for _, row in target_df.iterrows():
                offset = int(row["offset"])
                f.seek(offset + 3)
                data_bytes = f.read(fmt_size)
                try:
                    values = struct.unpack(struct_fmt, data_bytes)
                    decoded_rows.append(values)
                except struct.error:
                    continue

        if not decoded_rows:
            raise ValueError(f"No decodable messages found for '{filter_name}'.")

        # --- Handle mismatch between field names and unpacked data ---
        num_cols = len(decoded_rows[0])
        if len(field_names) < num_cols:
            field_names += [f"field_{i}" for i in range(len(field_names), num_cols)]
        elif len(field_names) > num_cols:
            field_names = field_names[:num_cols]

        decoded_df = pd.DataFrame(decoded_rows, columns=field_names)
        decoded_df.insert(0, "offset", target_df["offset"].values)
        decoded_df.insert(1, "type_id", target_df["type_id"].values)
        decoded_df.insert(2, "name", target_df["name"].values)

        # --- GPS auto conversions ---
        if filter_name.upper() == "GPS":
            lat_col = next((c for c in decoded_df.columns if c.lower() in ("lat", "field_7")), None)
            lon_col = next((c for c in decoded_df.columns if c.lower() in ("lng", "lon", "field_8")), None)
            alt_col = next((c for c in decoded_df.columns if c.lower() in ("alt", "field_9")), None)

            if lat_col and lon_col:
                decoded_df["Lat_deg"] = decoded_df[lat_col] / 1e7
                decoded_df["Lon_deg"] = decoded_df[lon_col] / 1e7
            if alt_col:
                decoded_df["Alt_m"] = decoded_df[alt_col].astype(float) / 100.0

        logger.info(f"Decoded {len(decoded_df)} '{filter_name}' messages")
        return decoded_df

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------
    def _parse_fmt_message(self, data: bytes, pos: int) -> int:
        """Extract one FMT definition and merge duplicates."""
        try:
            type_id = data[pos + 3]
            msg_len = data[pos + 4]
            if pos + msg_len > self.file_size:
                raise ValueError("FMT truncated")

            if msg_len < self.MIN_VALID_FMT_LEN:
                name = (
                    data[pos + 5 : pos + 9].decode("ascii", "ignore").rstrip("\x00")
                    if msg_len >= 9
                    else f"SHORT_{type_id}"
                )
                self.fmt_definitions[type_id] = (name, msg_len, "")
                return pos + 1

            name = data[pos + 5 : pos + 9].decode("ascii", "ignore").rstrip("\x00")
            ardu_fmt = data[pos + 9 : pos + 25].decode("ascii", "ignore").rstrip("\x00")
            raw_fields = data[pos + 25 : pos + msg_len].decode("ascii", "ignore").strip("\x00")
            field_names = [f.strip() for f in raw_fields.split(",") if f.strip()]

            prev_entry = self.fmt_definitions.get(type_id)
            prev_fields = self.fmt_field_names.get(name, [])
            if not prev_entry or len(field_names) > len(prev_fields):
                self.fmt_definitions[type_id] = (name, msg_len, ardu_fmt)
                self.fmt_field_names[name] = field_names

            self.total_msgs += 1
            return pos + msg_len

        except Exception as e:
            logger.debug(f"Skipped malformed FMT: {e}")
            self.skipped_msgs += 1
            return pos + 1

    def _parse_regular_message(self, data: bytes, pos: int, msg_type: int) -> int:
        """Parse standard message (metadata only)."""
        try:
            name, msg_len, _ = self.fmt_definitions[msg_type]
            if pos + msg_len > self.file_size:
                raise ValueError("Message truncated")

            self.messages_data.append(
                {"offset": pos, "type_id": msg_type, "name": name, "length": msg_len}
            )
            self.msg_statistics[name] += 1
            self.total_msgs += 1
            return pos + msg_len

        except Exception:
            self.skipped_msgs += 1
            return pos + 1

    def _convert_fmt_to_struct(self, ardu_fmt: str) -> str:
        """Convert ArduPilot format string to Python struct format."""
        type_map = {
            "b": "b", "B": "B", "h": "h", "H": "H",
            "i": "i", "I": "I", "q": "q", "Q": "Q",
            "f": "f", "d": "d",
            "c": "h", "C": "H", "e": "i", "E": "I",
            "L": "i", "M": "B",
            "n": "4s", "N": "16s", "Z": "64s", "a": "32h",
        }
        return "<" + "".join(type_map.get(ch, "") for ch in ardu_fmt)
