import time
import struct
from typing import Dict, List, Tuple, Optional
import pandas as pd


class BinLogParser:
    SYNC_BYTES = b"\xA3\x95"
    FMT_TYPE_ID = 0x80
    MIN_VALID_FMT_LEN = 16
    MAX_MESSAGES = 8_000_000

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.fmt_definitions: Dict[int, Tuple[str, int, str]] = {}
        self.fmt_field_names: Dict[str, List[str]] = {}
        self._struct_cache: Dict[str, Tuple[str, int]] = {}

        self.offsets: List[int] = []
        self.message_types: List[int] = []
        self.message_names: List[str] = []
        self.message_lengths: List[int] = []

        self.total_msgs = 0
        self.file_size = 0
        self.parse_time: Optional[float] = None

    def parse(self, max_msgs: Optional[int] = None) -> None:
        start = time.perf_counter()
        max_msgs = max_msgs or self.MAX_MESSAGES

        with open(self.file_path, "rb") as f:
            data = f.read()

        self.file_size = len(data)
        self.fmt_definitions[self.FMT_TYPE_ID] = ("FMT", 89, "BBI4s16s64s")

        index = 0
        while index < self.file_size - 3 and self.total_msgs < max_msgs:
            if data[index:index + 2] == self.SYNC_BYTES:
                msg_type = data[index + 2]

                if msg_type == self.FMT_TYPE_ID:
                    type_id = data[index + 3]
                    msg_len = data[index + 4]

                    if index + msg_len <= self.file_size and msg_len >= self.MIN_VALID_FMT_LEN:
                        name = data[index + 5:index + 9].decode("ascii", "ignore").rstrip("\x00")
                        ardu_fmt = data[index + 9:index + 25].decode("ascii", "ignore").rstrip("\x00")
                        field_names = data[index + 25:index + msg_len].decode("ascii", "ignore").strip("\x00").split(
                            ",")

                        self.fmt_field_names[name] = field_names
                        self.fmt_definitions[type_id] = (name, msg_len, ardu_fmt)
                        self.total_msgs += 1
                        index += msg_len
                    else:
                        index += 1

                elif msg_type in self.fmt_definitions:
                    name, msg_len, _ = self.fmt_definitions[msg_type]
                    if index + msg_len <= self.file_size:
                        self.offsets.append(index)
                        self.message_types.append(msg_type)
                        self.message_names.append(name)
                        self.message_lengths.append(msg_len)
                        self.total_msgs += 1
                        index += msg_len
                    else:
                        index += 1
                else:
                    index += 1
            else:
                index += 1

        self.parse_time = time.perf_counter() - start
        print(f"✅ Parsed {self.total_msgs:,} messages in {self.parse_time:.2f}s")

    def to_dataframe(self) -> Tuple[pd.DataFrame, Dict[str, float]]:
        start = time.perf_counter()
        df = pd.DataFrame({
            "offset": self.offsets,
            "type_id": self.message_types,
            "name": self.message_names,
            "length": self.message_lengths,
        })
        elapsed = time.perf_counter() - start
        print(f"✅ DataFrame created in {elapsed:.2f}s with {len(df):,} rows")
        return df, {"rows": len(df), "df_write_time_sec": elapsed}

    def decode_messages(self, gps_only: bool = False):
        with open(self.file_path, "rb") as f:
            data = f.read()

        start = time.perf_counter()
        decoded_messages = []

        indices = (
            [i for i, name in enumerate(self.message_names) if "GPS" in name]
            if gps_only
            else range(len(self.offsets))
        )

        struct_unpack = struct.unpack
        struct_calcsize = struct.calcsize
        cache = self._struct_cache
        fmt_defs = self.fmt_definitions

        for i in indices:
            msg_type = self.message_types[i]
            offset = self.offsets[i]
            msg_def = fmt_defs.get(msg_type)

            if not msg_def or not msg_def[2]:
                continue

            name, _, ardu_fmt = msg_def

            if ardu_fmt in cache:
                struct_fmt, fmt_size = cache[ardu_fmt]
            else:
                struct_fmt = self._convert_fmt_to_struct(ardu_fmt)
                fmt_size = struct_calcsize(struct_fmt)
                cache[ardu_fmt] = (struct_fmt, fmt_size)

            try:
                start_pos = offset + 3
                chunk = data[start_pos:start_pos + fmt_size]
                values = struct_unpack(struct_fmt, chunk)
                decoded_messages.append({
                    "name": name,
                    "type_id": msg_type,
                    "offset": offset,
                    "values": values
                })
            except struct.error:
                pass

        elapsed = time.perf_counter() - start
        print(f"✅ Decoded {len(decoded_messages):,} messages in {elapsed:.2f}s")
        return decoded_messages, elapsed

    def _convert_fmt_to_struct(self, ardu_fmt: str) -> str:
        type_map = {
            'b': 'b', 'B': 'B', 'h': 'h', 'H': 'H',
            'i': 'i', 'I': 'I', 'q': 'q', 'Q': 'Q',
            'f': 'f', 'd': 'd', 'c': 'h', 'C': 'H',
            'e': 'i', 'E': 'I', 'L': 'i', 'M': 'B',
            'n': '4s', 'N': '16s', 'Z': '64s', 'a': '32h'
        }
        return '<' + ''.join(type_map.get(ch, '') for ch in ardu_fmt)


if __name__ == "__main__":
    parser = BinLogParser("log_file_test_01.bin")
    parser.parse()

    messages, decode_time = parser.decode_messages()

    print(f"\n📊 Performance Summary:")
    print(f"Parse time: {parser.parse_time:.2f}s")
    print(f"Decode time: {decode_time:.2f}s")
    print(f"Total messages: {parser.total_msgs:,}")