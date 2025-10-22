# Flight Log Viewer

## Overview

**Flight Log Viewer** is a desktop application built with [Flet](https://flet.dev) that lets you load **ArduPilot flight log (.BIN)** or CSV files, parse their GPS telemetry, and visualize the flight path on an interactive map.

The app parses the raw log data using `pymavlink`, converts each GPS message into a `FlightPoint` object, and displays the route with flight statistics (duration, altitude range, number of points, etc.).

---

## 📁 Project Structure

```
Bin_files_loader/
│
├── main.py                      # Entry point of the application
│
├── config.json                  # Central configuration for UI, logging, and map
│
├── src/
│   ├── business_logic/
│   │   ├── flight_log_parser.py # Parses ArduPilot .BIN logs into FlightPoint objects
│   │   └── models.py            # Defines FlightPoint model (lat, lon, alt, timestamp)
│   │
│   ├── gui/
│   │   ├── app_manager.py       # Coordinates app lifecycle and navigation
│   │   ├── error_handler.py     # Displays modal error dialogs
│   │   └── views/
│   │       ├── home_view.py     # File picker and loading progress display
│   │       └── map_view.py      # Interactive map display of flight data
│   │
│   └── utils/
│       ├── config_loader.py     # Loads config.json into a Box object for easy access
│       ├── logger.py            # Sets up the logger (writes to logs/flight_viewer.log)
│       └── log_config.py        # Alternate simple logger setup
│
└── requirements.txt              # Project dependencies
```

---

## 🧩 Core Components

| Component           | Responsibility                                                                                       |
| ------------------- | ---------------------------------------------------------------------------------------------------- |
| **AppManager**      | Main controller that manages app startup, navigation, and background file loading.                   |
| **HomeView**        | UI screen with file picker and progress indicator. Calls `AppManager.handle_load_request()`.         |
| **MapView**         | Displays the parsed GPS path with OpenStreetMap tiles, markers, and flight statistics.               |
| **FlightLogParser** | Uses `pymavlink` to extract GPS data from `.BIN` files and converts them into `FlightPoint` objects. |
| **FlightPoint**     | A Pydantic model representing a single GPS telemetry record.                                         |
| **ErrorDialog**     | Utility for displaying error messages or retry dialogs in the UI.                                    |

---

## ⚙️ Configuration

All configurable options are stored in **`config.json`**, including:

* **App window settings** (title, size, padding)
* **Map display** (tile source URL, zoom, polyline sampling)
* **Logging behavior** (log file name, format, and level)

Example snippet from `config.json`:

```json
{
  "logging": {
    "file_name": "flight_viewer.log",
    "level": "INFO",
    "dir": "logs",
    "format": "%(asctime)s | %(levelname)-8s | %(message)s"
  }
}
```

---

## 🪄 Installation & Running

### 1. Clone the repository

```bash
git clone https://github.com/mendikup/Bin_files_loader.git
cd Bin_files_loader
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
python -m main
```

---

## 🧠 Notes

* The app supports **background parsing** with progress updates to avoid UI freezing.
* Logs are automatically written to the `logs/` directory.
* Future improvements may include better CSV handling and enhanced error dialogs.

---

**Developed by Mendikup** ✈️
