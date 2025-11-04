import time
import mmap
from pymavlink import mavutil
from bin_log_parser import BinLogParser
from parallal_decoder import ParallelBinDecoder


# ==========================================
# 🔧 הגדרות כלליות
# ==========================================
LOG_FILE = "log_file_test_01.bin"
COMPARE_MODE = "values"  # "speed" או "values"
SAMPLE_LIMIT = 500       # כמה הודעות לקחת מכל סוג
NUM_WORKERS = 8          # כמה תהליכים במקביל (רק ל-mode speed)
TARGET_MESSAGES = None   # None = כל סוגי ההודעות


# ==========================================
# 🧩 pymavlink decoder
# ==========================================
def decode_with_mavlink(file_path, target_messages=None, sample_limit=500):
    """Decode log with pymavlink (מגדיר מדגם לפי סוגים)."""
    connection = mavutil.mavlink_connection(file_path)
    decoded = {}
    seen_types = set()
    count = 0
    start_time = time.perf_counter()

    while True:
        msg = connection.recv_match(blocking=False)
        if msg is None:
            break
        msg_type = msg.get_type()
        count += 1

        # הוספת סוג הודעה חדש אוטומטית אם אין פילטר
        if target_messages is None:
            seen_types.add(msg_type)
            if msg_type not in decoded:
                decoded[msg_type] = []

        if target_messages is None or msg_type in decoded:
            if sample_limit is None or len(decoded[msg_type]) < sample_limit:
                decoded[msg_type].append(msg.to_dict())

    elapsed = time.perf_counter() - start_time
    print(f"✅ pymavlink decoded {count:,} messages in {elapsed:.2f}s")
    print(f"📋 Sampled {len(decoded)} message types ({sample_limit or 'ALL'} max per type)")
    return decoded


# ==========================================
# ⚙️ custom parallel parser - MODE: SPEED
# ==========================================
def decode_with_custom_speed(file_path, num_workers=8):
    """Decode log using the parallel decoder (speed test only)."""
    decoder = ParallelBinDecoder(file_path, num_workers=num_workers, round_floats=True)
    start_time = time.perf_counter()
    total_messages = decoder.run()
    elapsed = time.perf_counter() - start_time
    print(f"✅ custom parallel decoder finished in {elapsed:.2f}s ({total_messages:,} messages)")
    return total_messages


# ==========================================
# 🧠 custom parser - MODE: VALUES
# ==========================================
def decode_with_custom_values(file_path, target_messages=None, sample_limit=500):
    """Decode sample messages using the single-process BinLogParser."""
    decoded = {}
    message_filter = set(target_messages) if target_messages else None

    with open(file_path, "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            parser = BinLogParser(mapped, round_floats=True)
            parser.preload_fmt_messages()

            for msg in parser.decode_message_range(0, as_tuples=False, message_filter=message_filter):
                msg_type = msg["message_type"]
                if message_filter is None or msg_type in message_filter:
                    if msg_type not in decoded:
                        decoded[msg_type] = []
                    if sample_limit is None or len(decoded[msg_type]) < sample_limit:
                        decoded[msg_type].append(msg)

    total = sum(len(v) for v in decoded.values())
    print(f"✅ custom parser decoded {total:,} messages (non-parallel sample mode)")
    print(f"📋 Sampled {len(decoded)} message types ({sample_limit or 'ALL'} max per type)")
    return decoded


# ==========================================
# 🔍 השוואת פלטים
# ==========================================
def compare_data(mav_data, custom_data):
    """השוואה בין pymavlink לפענוח שלנו."""
    mav_types = set(mav_data.keys())
    custom_types = set(custom_data.keys())

    shared = mav_types & custom_types
    only_mav = mav_types - custom_types
    only_custom = custom_types - mav_types

    print("\n=== 🔍 Message Type Comparison ===")
    print(f"משותפים: {len(shared)}")
    print(f"נמצאים רק ב-pymavlink: {len(only_mav)} → {sorted(list(only_mav))[:10]}")
    print(f"נמצאים רק בפרסר שלנו: {len(only_custom)} → {sorted(list(only_custom))[:10]}")

    # דוגמה להשוואת תוכן הודעות ספציפיות
    print("\n=== 🧪 Comparing first message in GPS (אם קיים) ===")
    if "GPS" in shared:
        m1 = mav_data["GPS"][0]
        c1 = custom_data["GPS"][0]
        for k in sorted(set(m1.keys()) | set(c1.keys())):
            if k in m1 and k in c1 and m1[k] != c1[k]:
                print(f"⚠️ {k}: pymavlink={m1[k]} | ours={c1[k]}")


# ==========================================
# 🚀 MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print(f"Running comparison in mode: {COMPARE_MODE.upper()}")

    if COMPARE_MODE == "speed":
        start = time.perf_counter()
        mav_total = len(decode_with_mavlink(LOG_FILE))
        mav_time = time.perf_counter() - start

        start = time.perf_counter()
        custom_total = decode_with_custom_speed(LOG_FILE, NUM_WORKERS)
        custom_time = time.perf_counter() - start

        print("\n=== 📈 RESULTS ===")
        print(f"pymavlink: {mav_total:,} msgs in {mav_time:.2f}s")
        print(f"custom:    {custom_total:,} msgs in {custom_time:.2f}s")

    elif COMPARE_MODE == "values":
        mav_data = decode_with_mavlink(LOG_FILE, TARGET_MESSAGES, SAMPLE_LIMIT)
        custom_data = decode_with_custom_values(LOG_FILE, TARGET_MESSAGES, SAMPLE_LIMIT)
        compare_data(mav_data, custom_data)

    else:
        print("❌ COMPARE_MODE must be either 'speed' or 'values'")
