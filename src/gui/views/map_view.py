import logging
from pathlib import Path
from typing import List, Tuple

import flet as ft
import flet_map as fmap

from config.config_loader import load_config
from src.business_logic.models import FlightPoint

logger = logging.getLogger(__name__)

# ===============================================================
# Map constants
# ===============================================================

MAP_INITIAL_ZOOM = 11.0
MAP_HEIGHT = 700
MARKER_MAX_COUNT = 400

_MAP_CONFIG = load_config()
MAP_TILE_URL = _MAP_CONFIG["MAP_TILE_URL"]
POLYLINE_SAMPLE_INTERVAL = max(1, int(_MAP_CONFIG["POLYLINE_SAMPLE_INTERVAL"]))


class MapView(ft.Container):
    """Interactive map that displays a flight path and flight statistics."""

    def __init__(self, points: List[FlightPoint], source_file: Path):
        super().__init__()
        self._points = points
        self._source_file = source_file

        logger.info("Initializing map view for %s (%d points)", source_file.name, len(points))

        center_lat, center_lon = self._get_center_coordinates()
        polyline_layer = self._build_polyline_layer()
        markers = self._build_markers()
        flight_map = self._create_map(center_lat, center_lon, polyline_layer, markers)
        stats_panel = self._build_stats_panel()
        self.content = self._build_layout(flight_map, stats_panel)

    # ===============================================================
    # Core Map Building Steps
    # ===============================================================

    def _get_center_coordinates(self) -> Tuple[float, float]:
        """Return average (lat, lon) of all points."""
        if not self._points:
            return 0.0, 0.0
        avg_lat = sum(p.lat for p in self._points) / len(self._points)
        avg_lon = sum(p.lon for p in self._points) / len(self._points)
        logger.debug("Map center calculated: (%.6f, %.6f)", avg_lat, avg_lon)
        return avg_lat, avg_lon

    def _build_polyline_layer(self) -> fmap.PolylineLayer:
        """Create the blue flight path line on the map."""
        polyline_points = self._points[::POLYLINE_SAMPLE_INTERVAL]
        logger.debug(
            "Sampling %d of %d points for polyline (interval=%d)",
            len(polyline_points),
            len(self._points),
            POLYLINE_SAMPLE_INTERVAL,
        )

        polyline_marker = fmap.PolylineMarker(
            coordinates=[
                fmap.MapLatitudeLongitude(point.lat, point.lon) for point in polyline_points
            ],
            border_stroke_width=3,
            border_color=ft.Colors.BLUE,
            color=ft.Colors.with_opacity(0.6, ft.Colors.BLUE),
        )
        return fmap.PolylineLayer(polylines=[polyline_marker])

    def _build_markers(self) -> List[fmap.Marker]:
        """Add start, end, and intermediate markers on the map."""
        marker_sampling_interval = max(1, len(self._points) // MARKER_MAX_COUNT)
        markers = [
            fmap.Marker(
                content=ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.RED, size=18),
                coordinates=fmap.MapLatitudeLongitude(point.lat, point.lon),
            )
            for point in self._points[::marker_sampling_interval]
        ]

        if self._points:
            start, end = self._points[0], self._points[-1]
            logger.debug(
                "Start point: lat=%f lon=%f | End point: lat=%f lon=%f",
                start.lat, start.lon, end.lat, end.lon,
            )
            # Add start & end icons
            markers.insert(
                0,
                fmap.Marker(
                    content=ft.Icon(ft.Icons.FLIGHT_TAKEOFF, color=ft.Colors.GREEN, size=24),
                    coordinates=fmap.MapLatitudeLongitude(start.lat, start.lon),
                ),
            )
            markers.append(
                fmap.Marker(
                    content=ft.Icon(ft.Icons.FLIGHT_LAND, color=ft.Colors.ORANGE, size=24),
                    coordinates=fmap.MapLatitudeLongitude(end.lat, end.lon),
                )
            )
        logger.debug(
            "Plotted %d markers (interval=%d, max=%d)",
            len(markers), marker_sampling_interval, MARKER_MAX_COUNT,
        )
        return markers

    def _create_map(
        self, lat: float, lon: float, polyline_layer: fmap.PolylineLayer, markers: List[fmap.Marker]
    ) -> fmap.Map:
        """Assemble map layers and configuration."""
        return fmap.Map(
            expand=True,
            initial_center=fmap.MapLatitudeLongitude(lat, lon),
            initial_zoom=MAP_INITIAL_ZOOM,
            height=MAP_HEIGHT,
            interaction_configuration=fmap.MapInteractionConfiguration(
                flags=fmap.MapInteractiveFlag.ALL
            ),
            layers=[
                fmap.TileLayer(
                    url_template=MAP_TILE_URL,
                    on_image_error=lambda error: logger.error("Tile error: %s", error),
                ),
                polyline_layer,
                fmap.MarkerLayer(markers=markers),
            ],
        )

    # ===============================================================
    # Statistics Panel
    # ===============================================================

    def _compute_flight_stats(self) -> Tuple[float, float, float]:
        """Calculate duration (s), min altitude, and max altitude."""
        if not self._points:
            return 0.0, 0.0, 0.0
        duration = self._points[-1].ts - self._points[0].ts if len(self._points) > 1 else 0
        min_alt = min(p.alt for p in self._points)
        max_alt = max(p.alt for p in self._points)
        return duration, min_alt, max_alt

    def _build_stats_panel(self) -> ft.Container:
        """Create right-hand panel showing flight statistics."""
        duration, min_alt, max_alt = self._compute_flight_stats()

        stats = [
            ft.Text("Flight Statistics", size=16, weight=ft.FontWeight.BOLD),
            ft.Divider(height=1),
            ft.Text(f"File: {self._source_file.name}", size=12),
            ft.Text(f"Points: {len(self._points):,}", size=12),
            ft.Text(f"Duration: {duration:.1f}s", size=12),
            ft.Text(f"Altitude: {min_alt:.1f}m - {max_alt:.1f}m", size=12),
        ]

        return ft.Container(
            content=ft.Column(stats, spacing=5),
            padding=15,
            bgcolor=ft.Colors.ON_SURFACE_VARIANT,
            border_radius=10,
        )

    # ===============================================================
    # Final Layout Assembly
    # ===============================================================

    def _build_layout(self, flight_map: fmap.Map, stats_panel: ft.Container) -> ft.Column:
        """Combine title, map, and statistics into a single layout."""
        header = ft.Row(
            [
                ft.Text("Flight Path", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                stats_panel,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        return ft.Column(
            [header, ft.Container(flight_map, expand=True, border_radius=10)],
            expand=True,
            spacing=15,
        )
