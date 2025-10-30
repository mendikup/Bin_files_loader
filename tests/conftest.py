import struct
import re
import time


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

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.format_definitions = {}

    # --------------------------
    # שלב 1 - קריאת FMTs
    # --------------------------
    def parse_fmts(self):
        """
        Scan the BIN file quickly and extract all FMT message definitions.

        Stops automatically when no new FMT messages are found for a while,
        instead of relying on a fixed count.
        """
        with open(self.file_path, "rb") as file:
            file_bytes = file.read()

        start_time = time.time()
        position = 0
        file_size = len(file_bytes)
        fmt_count = 0
        no_new_found = 0

        while True:
            # חיפוש מהיר קדימה של רצף הסינכרון
            sync_index = file_bytes.find(self.SYNC_BYTES, position)
            if sync_index == -1 or sync_index + 3 >= file_size:
                break

            msg_type = file_bytes[sync_index + 2]

            # לא הודעת FMT → דלג קדימה
            if msg_type != self.FMT_TYPE_ID:
                # אם כבר יודעים את האורך של סוג ההודעה הזה, נקפוץ לפיו
                entry = self.format_definitions.get(msg_type)
                if entry:
                    position = sync_index + entry["msg_len"]
                else:
                    position = sync_index + 2
                continue

            # ודא שלא יצאנו מהקובץ
            if sync_index + self.FMT_MESSAGE_LENGTH > file_size:
                break

            type_id = file_bytes[sync_index + 3]

            # אם זה FMT חדש שעדיין לא נשמר
            if type_id not in self.format_definitions:
                message_length = file_bytes[sync_index + 4]
                message_name = file_bytes[sync_index + 5:sync_index + 9].decode("ascii", "ignore").strip("\x00")
                ardu_format = file_bytes[sync_index + 9:sync_index + 25].decode("ascii", "ignore").strip("\x00")
                raw_fields = file_bytes[sync_index + 25:sync_index + 89]
                field_names = self._clean_field_names(raw_fields)


                struct_format = self._build_struct_format(ardu_format)
                struct_size = struct.calcsize(struct_format)

                # שמירה של כל הנתונים הדרושים לפיענוח
                self.format_definitions[type_id] = {
                    "name": message_name,
                    "ardu_fmt": ardu_format,
                    "struct_fmt": struct_format,
                    "struct_size": struct_size,
                    "fields": field_names,
                    "msg_len": message_length,
                }

                fmt_count += 1
                no_new_found = 0  # איפוס – מצאנו חדש
            else:
                # כבר הכרנו את הפורמט הזה
                no_new_found += 1

            # קפיצה לסוף ההודעה הזאת
            position = sync_index + self.FMT_MESSAGE_LENGTH

            # אם לא נמצאו פורמטים חדשים במשך זמן רב – כנראה שסיימנו
            if no_new_found > 50:
                break

        elapsed = time.time() - start_time
        print(f"Finished parsing {fmt_count} FMT definitions in {elapsed:.2f}s")

    # --------------------------
    # שלב 2 - פיענוח הודעות רגילות
    # --------------------------
    def decode_all(self):
        """פענוח כל ההודעות בקובץ. הדפסת 10 הודעות GPS בלבד."""
        with open(self.file_path, "rb") as file:
            file_bytes = file.read()

        position = 0
        decoded_count = 0
        gps_printed = 0
        start_time = time.time()

        while position < len(file_bytes) - 3:
            if file_bytes[position:position + 2] != self.SYNC_BYTES:
                position += 1
                continue

            msg_type = file_bytes[position + 2]

            # דלג על הודעות FMT
            if msg_type == self.FMT_TYPE_ID:
                position += self.FMT_MESSAGE_LENGTH
                continue

            fmt_info = self.format_definitions.get(msg_type)
            if not fmt_info:
                position += 1
                continue

            payload_start = position + 3
            payload_end = payload_start + fmt_info["struct_size"]
            if payload_end > len(file_bytes):
                break

            decoded_values = list(struct.unpack(fmt_info["struct_fmt"], file_bytes[payload_start:payload_end]))

            # scaling לפי האותיות המקוריות של ArduPilot
            for index, fmt_char in enumerate(fmt_info["ardu_fmt"]):
                if index < len(decoded_values) and fmt_char in self.SCALE_MAP:
                    decoded_values[index] *= self.SCALE_MAP[fmt_char]

            message_dict = dict(zip(fmt_info["fields"], decoded_values))
            decoded_count += 1

            # הדפסה רק של GPS
            if fmt_info["name"] == "GPS" and gps_printed < 10:
                print(message_dict)
                gps_printed += 1

            position += fmt_info["msg_len"]

        elapsed = time.time() - start_time
        print(f"Decoded {decoded_count:,} messages in {elapsed:.2f}s")

    # --------------------------
    # עוזרים פנימיים
    # --------------------------
    def _clean_field_names(self, raw_bytes: bytes):
        """ניקוי רשימת שמות השדות מתוך 64 בתים"""
        text = raw_bytes.decode("ascii", "ignore")
        text = re.split(r"\x00{2,}", text)[0]
        text = text.strip("\x00").replace(" ", "")
        return [f for f in text.split(",") if f]

    def _build_struct_format(self, ardu_format: str) -> str:
        """המרת פורמט של ArduPilot לפורמט שהמודול struct יודע לקרוא."""
        py_fmt = "<"
        for fmt_char in ardu_format:
            mapped = self.STRUCT_MAP.get(fmt_char)
            if mapped:
                py_fmt += mapped
        return py_fmt


# --------------------------
# שימוש בסיסי
# --------------------------
# if __name__ == "__main__":
    # parser = SimpleBinParser("log_file_test_01.bin")
    # parser.parse_fmts()
    # parser.decode_all()




import pandas as pd
from pymavlink import mavutil
 # ← החלף לשם הקובץ שלך

FILE_PATH = "log_file_test_01.bin"
LIMIT = 500_000
MSG_TYPE = "GPS"


def read_with_pymavlink(file_path, limit=LIMIT):
    log = mavutil.mavlink_connection(file_path)
    data = []
    while len(data) < limit:
        msg = log.recv_match(type=MSG_TYPE, blocking=False)
        if msg is None:
            break
        data.append(msg.to_dict())
    df = pd.DataFrame(data)
    df.to_csv("gps_pymavlink.csv", index=False)
    print(f"✅ pymavlink: saved {len(df):,} messages to gps_pymavlink.csv")
    return df


def read_with_custom_parser(file_path, limit=LIMIT):
    parser = SimpleBinParser(file_path)
    parser.parse_fmts()
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    position = 0
    gps_rows = []
    while position < len(file_bytes) - 3 and len(gps_rows) < limit:
        if file_bytes[position:position + 2] != parser.SYNC_BYTES:
            position += 1
            continue
        msg_type = file_bytes[position + 2]
        if msg_type == parser.FMT_TYPE_ID:
            position += parser.FMT_MESSAGE_LENGTH
            continue

        fmt_info = parser.format_definitions.get(msg_type)
        if not fmt_info:
            position += 1
            continue

        if fmt_info["name"] != MSG_TYPE:
            position += fmt_info["msg_len"]
            continue

        start = position + 3
        end = start + fmt_info["struct_size"]
        values = list(struct.unpack(fmt_info["struct_fmt"], file_bytes[start:end]))

        for idx, ch in enumerate(fmt_info["ardu_fmt"]):
            if idx < len(values) and ch in parser.SCALE_MAP:
                values[idx] *= parser.SCALE_MAP[ch]

        gps_rows.append(dict(zip(fmt_info["fields"], values)))
        position += fmt_info["msg_len"]

    df = pd.DataFrame(gps_rows)
    df.to_csv("gps_custom.csv", index=False)
    print(f"✅ custom parser: saved {len(df):,} messages to gps_custom.csv")
    return df


def compare_csvs():
    df1 = pd.read_csv("gps_pymavlink.csv")
    df2 = pd.read_csv("gps_custom.csv")

    # מיון לפי זמן
    df1.sort_values("TimeUS", inplace=True)
    df2.sort_values("TimeUS", inplace=True)

    # איחוד לפי זמן
    merged = pd.merge(df1, df2, on="TimeUS", suffixes=("_mav", "_custom"))

    # חישוב סטיות ממוצעות
    diffs = {
        "Lat_diff": (merged["Lat_mav"] - merged["Lat_custom"]).abs().mean(),
        "Lng_diff": (merged["Lng_mav"] - merged["Lng_custom"]).abs().mean(),
        "Alt_diff": (merged["Alt_mav"] - merged["Alt_custom"]).abs().mean(),
        "Spd_diff": (merged["Spd_mav"] - merged["Spd_custom"]).abs().mean(),
    }

    print("📊 Mean absolute differences:")
    for k, v in diffs.items():
        print(f"{k:<10}: {v:.8f}")

    merged.to_csv("gps_comparison_merged.csv", index=False)
    print("✅ Saved merged comparison to gps_comparison_merged.csv")


if __name__ == "__main__":
    print("🔹 Extracting 500k GPS messages with pymavlink...")
    read_with_pymavlink(FILE_PATH)
    print("\n🔹 Extracting 500k GPS messages with custom parser...")
    read_with_custom_parser(FILE_PATH)
    print("\n🔹 Comparing results...")
    compare_csvs()


