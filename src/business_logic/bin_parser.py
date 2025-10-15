from pymavlink import mavutil
from pathlib import Path
from drone_flet_basic.src.business_logic.models import FlightPoint

def parse_ardupilot_bin(path: Path):
    log = mavutil.mavlink_connection(str(path))
    count = 0

    while True:
        msg = log.recv_match(blocking=False)
        if msg is None:
            break

        if msg.get_type() == "GPS":
            count += 1
            if count % 500 == 0:
                print(f"Parsed {count} GPS points...")

            yield FlightPoint(
                lat=msg.Lat / 1e7,
                lon=msg.Lng / 1e7,
                alt=msg.Alt / 100.0,
                ts=msg.TimeUS / 1e6,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
            )

    print(f"Finished parsing {count} GPS points.")
    log.close()
