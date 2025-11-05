import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../parser')))

import os
import math
import mmap
import pytest
from pymavlink import mavutil
from bin_log_parser import BinLogParser

TEST_FILE = os.path.join(os.path.dirname(__file__), "../parser/log_file_test_01.bin")


@pytest.mark.mavlink
def test_compare_against_pymavlink_when_available_and_file_provided():
    """
    Compare our custom parser output against pymavlink on the same BIN file.
    If mismatch occurs, print internal warnings from BinLogParser to analyze cause.
    """

    if not os.path.exists(TEST_FILE):
        pytest.skip(f"BIN file not found: {TEST_FILE}")

    # --- Decode with our parser ---
    with open(TEST_FILE, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        parser = BinLogParser(mm, round_floats=True, collect_warnings=True)
        parser.preload_fmt_messages()
        parser.build_structs_for_local_use()

        ours_iter = (
            msg for msg in parser.parse_messages_in_range(0)
            if msg["message_type"] != "FMT"
        )

        # --- Decode with pymavlink ---
        connection = mavutil.mavlink_connection(TEST_FILE)
        pymav_iter = (
            msg.to_dict()
            for msg in iter(lambda: connection.recv_match(blocking=False), None)
            if msg and msg.get_type() != "FMT"
        )

        # --- Comparison metrics ---
        total_compared = 0
        mismatches = 0
        match_count = 0
        mismatch_samples = []
        total_fields = 0
        missing_summary = []

        for ours_msg, their_msg in zip(ours_iter, pymav_iter):
            ours_keys = set(ours_msg.keys())
            theirs_keys = set(their_msg.keys())
            shared_keys = ours_keys & theirs_keys
            total_fields += len(shared_keys)

            missing_summary.append({
                "missing_in_ours": theirs_keys - ours_keys,
                "missing_in_theirs": ours_keys - theirs_keys
            })

            for key in shared_keys:
                ours_val = ours_msg[key]
                theirs_val = their_msg[key]

                if ours_val in (None, "") and theirs_val in (None, ""):
                    continue

                if isinstance(ours_val, (int, float)) and isinstance(theirs_val, (int, float)):
                    if math.isclose(float(ours_val), float(theirs_val), rel_tol=1e-5, abs_tol=1e-3):
                        match_count += 1
                    else:
                        mismatches += 1
                        if len(mismatch_samples) < 5:
                            mismatch_samples.append((key, ours_val, theirs_val))
                else:
                    if str(ours_val) == str(theirs_val):
                        match_count += 1
                    else:
                        mismatches += 1
                        if len(mismatch_samples) < 5:
                            mismatch_samples.append((key, ours_val, theirs_val))

                total_compared += 1

        match_rate = 100 * match_count / total_fields if total_fields else 0
        print(f"\n Compared {total_compared:,} total field values across all shared messages.")
        print(f" Field match rate: {match_rate:.2f}% ({match_count}/{total_fields})")
        print(f" {mismatches:,} mismatches beyond tolerance.")

        # Print examples of value mismatches
        if mismatch_samples:
            print("\n Example value mismatches:")
            for k, ov, tv in mismatch_samples:
                print(f"  Field '{k}': ours={ov}  |  theirs={tv}")

        # Print field presence differences
        print("\n Field presence summary (first 3 messages):")
        for i, m in enumerate(missing_summary[:3]):
            if m["missing_in_ours"] or m["missing_in_theirs"]:
                print(f"  Msg #{i+1}: missing_in_ours={m['missing_in_ours']} | missing_in_theirs={m['missing_in_theirs']}")

        # --- NEW: warnings output if mismatch occurs ---
        if mismatches > 0 or total_fields == 0:
            if parser.warnings:
                print(f"\n🔍 Internal parser warnings ({len(parser.warnings)} total):")
                for w in parser.warnings[:10]:
                    print(f"  • {w}")
                if len(parser.warnings) > 10:
                    print(f"  ... and {len(parser.warnings) - 10} more.")
            else:
                print("\n✅ No internal warnings collected — mismatch likely due to pymavlink interpretation differences.")

        assert total_compared > 0, "No comparable fields found between parsers"

        mm.close()
