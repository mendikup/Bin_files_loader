from pydantic import BaseModel, Field


class FlightPoint(BaseModel):
    """Single GPS telemetry point from a flight log."""

    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    alt: float = Field(..., description="Altitude in meters above mean sea level")
    ts: float = Field(..., description="Timestamp in seconds from log start")
