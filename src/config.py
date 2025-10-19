# src/config.py

# --- Application Configuration ---
APP_TITLE = "Flight Log Viewer"
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 700
PAGE_PADDING = 20

# --- Map Configuration ---
MAP_INITIAL_ZOOM = 13.0
MAP_HEIGHT = 700
MAP_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
POLYLINE_SAMPLE_INTERVAL = 10  # Sample every 10th point for the trajectory
MARKER_MAX_COUNT = 400         # Maximum number of markers to show (approx)

# --- Data Processing Constants ---
# ArduPilot .BIN log specific values
GPS_NORM_SCALE_FACTOR = 1e7  # Factor for normalizing Lat/Lon from older logs (1e7)
ALTITUDE_DIVISOR = 100.0     # Altitude divisor (cm to meters)
TIMESTAMP_DIVISOR = 1e6      # Time divisor (microseconds to seconds)
GPS_PROGRESS_REPORT_INTERVAL = 500  # Report progress every N points during BIN parsing