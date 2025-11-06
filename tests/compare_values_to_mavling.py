import struct
import re
import time
import math


class SimpleBinParser:
    SYNC_BYTES = b"\xA3\x95"
    FMT_TYPE_ID = 0x80
    FMT_MESSAGE_LENGTH = 89

    STRUCT_MAP = {
        "a": "32h",
        "b": "b", "B": "B",
        "h": "h", "H": "H",
        "i": "i", "I": "I",
        "q": "q", "Q": "Q",
        "f": "f", "d": "d",
        "n": "4s", "N": "16s", "Z": "64s",
        "c": "h", "C": "H",   # ×100
        "e": "i", "E": "I",   # ×100
        "L": "i", "M": "B",   # L=lat/lon 1e-7 deg, M=mode
    }

    SCALE_MAP = {
        "c": 0.01,
        "C": 0.01,
        "e": 0.01,
        "E": 0.01,
        "L": 1e-7,
    }

    ROUNDING_COLUMNS = {
        "Lat", "Lng", "TLat", "TLng", "Pitch", "Roll", "Yaw", "VDop", "HDop", "VAcc",
        "HAcc", "Alt", "RelHomeAlt", "RelOriginAlt", "VZ", "Spd", "GCrs", "GZ", "Q1", "Q2", "Q3", "Q4"
    }

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.format_definitions = {}

    # --------------------------
    # שלב 1 - קריאת FMT בהתחלה
    # --------------------------
    def parse_fmts(self):
        """קורא את כל הודעות ה-FMT הראשוניות"""
        with open(self.file_path, "rb") as f:
            data = f.read()

        pos = 0
        file_size = len(data)
        fmt_count = 0
        no_new_found = 0
        start = time.time()

        while True:
            sync_index = data.find(self.SYNC_BYTES, pos)
            if sync_index == -1 or sync_index + 3 >= file_size:
                break

            msg_type = data[sync_index + 2]
            if msg_type != self.FMT_TYPE_ID:
                entry = self.format_definitions.get(msg_type)
                pos = sync_index + (entry["msg_len"] if entry else 2)
                continue

            if sync_index + self.FMT_MESSAGE_LENGTH > file_size:
                break

            parsed_fmt = self._parse_single_fmt(data, sync_index)
            if parsed_fmt:
                self.format_definitions[parsed_fmt["type_id"]] = parsed_fmt
                fmt_count += 1
                no_new_found = 0
            else:
                no_new_found += 1

            pos = sync_index + self.FMT_MESSAGE_LENGTH
            if no_new_found > 50:
                break

        print(f"✅ Parsed {fmt_count} FMT definitions in {time.time() - start:.2f}s")

    # --------------------------
    # שלב 2 - פיענוח הודעות (עם FMT דינמי)
    # --------------------------
    def decode_all(self, max_messages=None):
        """מפענח את כל ההודעות מהקובץ ומעדכן FMTים חדשים תוך כדי"""
        with open(self.file_path, "rb") as f:
            data = f.read()

        pos = 0
        decoded = {}
        total_msgs = 0
        file_size = len(data)

        while pos < file_size - 3:
            if data[pos:pos + 2] != self.SYNC_BYTES:
                pos += 1
                continue

            msg_id = data[pos + 2]

            # ✅ אם מצאנו FMT חדש תוך כדי — נעדכן אותו
            if msg_id == self.FMT_TYPE_ID:
                parsed_fmt = self._parse_single_fmt(data, pos)
                if parsed_fmt:
                    type_id = parsed_fmt["type_id"]
                    if type_id not in self.format_definitions:
                        print(f"🆕 Found NEW FMT '{parsed_fmt['name']}' (type={type_id}) at position {pos}")
                        self.format_definitions[type_id] = parsed_fmt
                pos += self.FMT_MESSAGE_LENGTH
                continue

            fmt = self.format_definitions.get(msg_id)
            if not fmt:
                pos += 1
                continue

            start = pos + 3
            end = start + fmt["struct_size"]
            if end > file_size:
                break

            try:
                values = list(struct.unpack(fmt["struct_fmt"], data[start:end]))
            except struct.error:
                pos += 1
                continue

            # Scaling
            for i, ch in enumerate(fmt["ardu_fmt"]):
                if ch in self.SCALE_MAP and i < len(values):
                    values[i] *= self.SCALE_MAP[ch]

            msg = {}
            for i, field in enumerate(fmt["fields"]):
                if i >= len(values):
                    msg[field] = None
                    continue

                val = values[i]
                val = self._round_if_needed(val, field, fmt["name"])

                if isinstance(val, (bytes, bytearray)):
                    val = val.decode("ascii", "ignore").rstrip("\x00")
                    if field == "Data" and not any(values[i]):
                        val = None

                if isinstance(val, float) and (math.isnan(val) or val == float("inf")):
                    val = None

                msg[field] = val

            decoded.setdefault(fmt["name"], []).append(msg)
            total_msgs += 1
            pos += fmt["msg_len"]

            if max_messages and total_msgs >= max_messages:
                break

        return decoded

    # --------------------------
    # פונקציית עזר: פיענוח הודעת FMT אחת
    # --------------------------
    def _parse_single_fmt(self, data: bytes, pos: int):
        """מפענח הודעת FMT אחת בזמן ריצה ומחזיר dict עם המבנה"""
        try:
            type_id = data[pos + 3]
            msg_len = data[pos + 4]
            name = data[pos + 5:pos + 9].decode("ascii", "ignore").strip("\x00")
            ardu_fmt = data[pos + 9:pos + 25].decode("ascii", "ignore").strip("\x00")
            raw_fields = data[pos + 25:pos + 89]
            fields = self._clean_field_names(raw_fields)

            struct_fmt = self._build_struct_format(ardu_fmt)
            struct_size = struct.calcsize(struct_fmt)

            return {
                "type_id": type_id,
                "name": name,
                "ardu_fmt": ardu_fmt,
                "struct_fmt": struct_fmt,
                "struct_size": struct_size,
                "fields": fields,
                "msg_len": msg_len,
            }
        except Exception:
            return None

    # --------------------------
    # פונקציות עזר נוספות
    # --------------------------
    def _round_if_needed(self, val, col, mavpackettype):
        if isinstance(val, float):
            if col in self.ROUNDING_COLUMNS or (mavpackettype == "GPS" and col == "Alt"):
                return round(val, 7)
        return val

    def _clean_field_names(self, raw_bytes: bytes):
        text = raw_bytes.decode("ascii", "ignore")
        text = re.split(r"\x00{2,}", text)[0]
        text = text.strip("\x00").replace(" ", "")
        return [f for f in text.split(",") if f]

    def _build_struct_format(self, ardu_format: str) -> str:
        py_fmt = "<"
        for fmt_char in ardu_format:
            mapped = self.STRUCT_MAP.get(fmt_char)
            if mapped:
                py_fmt += mapped
        return py_fmt



from pymavlink import mavutil

# --------------------------------------------------------------
def compare_with_pymavlink(file_path, sample_limit=2000, tolerance=1e-3):
    print(f"\n🔹 Comparing up to {sample_limit:,} samples per message type...\n")

    log = mavutil.mavlink_connection(file_path)
    mav_msgs = {}
    while True:
        msg = log.recv_match(blocking=False)
        if msg is None:
            break
        name = msg.get_type()
        mav_msgs.setdefault(name, []).append(msg.to_dict())
        if len(mav_msgs[name]) >= sample_limit:
            continue

    parser = SimpleBinParser(file_path)
    parser.parse_fmts()
    my_msgs = parser.decode_all(max_messages=len(mav_msgs) * sample_limit * 2)

    print(f"✅ pymavlink found {len(mav_msgs)} types, custom parser {len(my_msgs)} types\n")

    # check missing types
    only_mav = set(mav_msgs) - set(my_msgs)
    only_mine = set(my_msgs) - set(mav_msgs)
    if only_mav:
        print(f"⚠️ Missing in custom parser: {sorted(only_mav)}")
    if only_mine:
        print(f"⚠️ Extra in custom parser: {sorted(only_mine)}")
    print()

    for name in sorted(set(mav_msgs) & set(my_msgs)):
        m1 = mav_msgs[name]
        m2 = my_msgs[name]
        n = min(len(m1), len(m2))
        diffs = 0
        for i in range(n):
            d1, d2 = m1[i], m2[i]
            for k in d2:
                if k not in d1:
                    continue
                v1, v2 = d1[k], d2[k]
                if isinstance(v1, (float, int)) and isinstance(v2, (float, int)):
                    if abs(float(v1) - float(v2)) > tolerance:
                        diffs += 1
                        break
                elif v1 != v2:
                    diffs += 1
                    break
        if diffs == 0:
            print(f"✅ {name:<10} identical ({n:,})")
        else:
            pct = diffs / n * 100
            print(f"⚠️ {name:<10} → {pct:.2f}% differing ({diffs:,}/{n:,})")
            # show one diff example
            for k in d2.keys():
                if k in d1 and d1[k] != d2[k]:
                    print(f"   field {k}: my={d2[k]} | mav={d1[k]}")
                    break


if __name__ == "__main__":
    FILE_PATH = "../test_parsers/log_file_test_01.bin"
    compare_with_pymavlink(FILE_PATH, sample_limit=2000)
