from __future__ import annotations

from pydantic import BaseModel, Field

class FlightPoint(BaseModel):
    """Represents a single telemetry sample along the flight path."""
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    alt: float = Field(..., description="Altitude in meters (AMSL)")
    ts: float = Field(..., description="Timestamp in seconds from log start")
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
