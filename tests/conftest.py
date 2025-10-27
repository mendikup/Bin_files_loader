import json
import time
import struct
from collections import Counter
from typing import Dict, List, Tuple, Optional
import pandas as pd


class BinLogParser:
    """
    Parser for ArduPilot .BIN log files.

    - Detects FMT messages and extracts message definitions
    - Collects metadata for all log messages
    - Supports saving parsed data to JSON and Pandas DataFrame
    - Can decode specific message types (e.g., GPS) into real numeric values
    """

    SYNC_BYTES = b"\xA3\x95"
    FMT_TYPE_ID = 0x80
    MAX_MESSAGES = 8_000_000
    MIN_VALID_FMT_LEN = 16
    EXPECTED_FMT_COUNT = 180

    def __init__(self, file_path: str):
        """
        Initialize a parser instance for a specific binary log file.
        """
        self.file_path = file_path
        self.fmt_definitions: Dict[int, Tuple[str, int, str]] = {}
        self.msg_statistics: Counter = Counter()
        self.messages_data: List[Dict] = []
        self.total_msgs: int = 0
        self.skipped_msgs: int = 0
        self.file_size: int = 0
        self.parse_time: Optional[float] = None
        self.json_write_time: Optional[float] = None
        self.df_write_time: Optional[float] = None
        self.fmt_field_names: Dict[str, List[str]] = {}

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def parse(self, max_msgs: Optional[int] = None) -> None:
        """
        Parse the binary file, detecting FMT definitions and message metadata.
        """
        start_time = time.perf_counter()
        max_msgs = max_msgs or self.MAX_MESSAGES

        try:
            with open(self.file_path, "rb") as f:
                data = f.read()
        except (FileNotFoundError, PermissionError, OSError) as e:
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
            raise RuntimeError(f"Unexpected parsing error: {e}")

        self.parse_time = time.perf_counter() - start_time

    def to_json(self, output_path: str) -> Dict[str, float]:
        """
        Save the parsed results to a JSON file.
        Returns a dict containing write time and summary statistics.
        """
        if not self.messages_data:
            raise ValueError("No messages parsed. Run parse() first.")

        start = time.perf_counter()
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
        return {
            "json_write_time_sec": self.json_write_time,
            "total_messages": self.total_msgs,
            "skipped_messages": self.skipped_msgs,
        }

    def to_dataframe(self) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Convert parsed message metadata into a Pandas DataFrame.
        Returns the DataFrame and a dict with generation time.
        """
        if not self.messages_data:
            raise ValueError("No messages parsed. Run parse() first.")

        start = time.perf_counter()
        df = pd.DataFrame(self.messages_data)
        self.df_write_time = time.perf_counter() - start
        return df, {"df_write_time_sec": self.df_write_time, "rows": len(df)}

    # ---------------------------------------------------------------------
    # Decode messages into actual numeric values using FMT field names
    # ---------------------------------------------------------------------

    def decode_all_messages_to_csv(self, output_path="decoded_all.csv", batch_size=50000):
        """
        Decode all messages and write directly to CSV in batches
        to avoid memory overflow.
        """
        import struct
        import pandas as pd
        import time

        if not self.fmt_definitions or not self.messages_data:
            raise ValueError("No parsed data found. Run parse() first.")

        start = time.perf_counter()
        rows = []
        total_written = 0
        header_written = False

        with open(self.file_path, "rb") as f:
            for i, msg in enumerate(self.messages_data, start=1):
                fmt_entry = self.fmt_definitions.get(msg["type_id"])
                if not fmt_entry or not fmt_entry[2]:
                    continue

                name = msg["name"]
                ardu_fmt = fmt_entry[2]
                struct_fmt = self._convert_fmt_to_struct(ardu_fmt)
                fmt_size = struct.calcsize(struct_fmt)

                f.seek(msg["offset"] + 3)
                try:
                    values = struct.unpack(struct_fmt, f.read(fmt_size))
                except struct.error:
                    continue

                field_names = self.fmt_field_names.get(name, [])
                if len(field_names) != len(values):
                    field_names = [f"field_{i}" for i in range(len(values))]

                row = {"name": name}
                row.update({k: v for k, v in zip(field_names, values)})
                rows.append(row)

                if len(rows) >= batch_size:
                    df = pd.DataFrame(rows)
                    df.to_csv(output_path, index=False, mode="a", header=not header_written)
                    header_written = True
                    total_written += len(df)
                    rows.clear()

            # write remaining rows
            if rows:
                df = pd.DataFrame(rows)
                df.to_csv(output_path, index=False, mode="a", header=not header_written)
                total_written += len(df)

        print(f"✅ Decoded and saved {total_written:,} messages to '{output_path}' "
              f"in {time.perf_counter() - start:.2f} seconds")

    # ---------------------------------------------------------------------
    # Internal Helpers
    # ---------------------------------------------------------------------

    def _parse_fmt_message(self, data: bytes, pos: int) -> int:
        """
        Parse an FMT message that defines structure of other messages.
        Returns the next position to continue scanning.
        """
        try:
            type_id = data[pos + 3]
            msg_len = data[pos + 4]
            if pos + msg_len > self.file_size:
                raise ValueError("FMT truncated")

            if msg_len < self.MIN_VALID_FMT_LEN:
                if msg_len >= 9:
                    name = data[pos + 5:pos + 9].decode("ascii", "ignore").rstrip("\x00")
                else:
                    name = f"SHORT_{type_id}"
                self.fmt_definitions[type_id] = (name, msg_len, "")
                next_index = pos + 1
            else:
                name = data[pos + 5:pos + 9].decode("ascii", "ignore").rstrip("\x00")
                ardu_fmt = data[pos + 9:pos + 25].decode("ascii", "ignore").rstrip("\x00")

                # Extract column names from the FMT definition itself
                field_names = (
                    data[pos + 25 : pos + msg_len]
                    .decode("ascii", "ignore")
                    .strip("\x00")
                    .split(",")
                )

                self.fmt_field_names[name] = field_names
                self.fmt_definitions[type_id] = (name, msg_len, ardu_fmt)
                next_index = pos + msg_len

            self.total_msgs += 1
            return next_index

        except Exception:
            self.skipped_msgs += 1
            return pos + 1

    def _parse_regular_message(self, data: bytes, pos: int, msg_type: int) -> int:
        """
        Parse a standard message using known FMT definitions.
        Returns the next position to continue scanning.
        """
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
        """
        Convert ArduPilot format string to Python struct format (little-endian).
        """
        type_map = {
            'b': 'b', 'B': 'B', 'h': 'h', 'H': 'H',
            'i': 'i', 'I': 'I', 'q': 'q', 'Q': 'Q',
            'f': 'f', 'd': 'd',
            'c': 'h', 'C': 'H',
            'e': 'i', 'E': 'I',
            'L': 'i', 'M': 'B',
            'n': '4s', 'N': '16s', 'Z': '64s',
            'a': '32h'
        }
        return '<' + ''.join(type_map.get(ch, '') for ch in ardu_fmt)


# parser = BinLogParser("log_file_test_01.bin")
# parser.parse()
# print(f"Parsed {parser.total_msgs:,} messages in {parser.parse_time:.2f} sec")
#
#
#
# # Convert to DataFrame
# df, stats_df = parser.to_dataframe()
# print(f"DataFrame created ({stats_df['rows']} rows) in {stats_df['df_write_time_sec']:.2f} sec")
#
# # Decode GPS messages to numeric values with field names
# decoded_gps = parser.decode_messages(df, "GPS")
# print(decoded_gps.head())



parser = BinLogParser("log_file_test_01.bin")
parser.parse()
df_all = parser.decode_all_messages_to_csv()
