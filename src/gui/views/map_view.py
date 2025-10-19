from pathlib import Path
from typing import List
import logging

import flet as ft
import flet_map as fmap

from src.business_logic.models import FlightPoint
from src.business_logic.utils.calculate_center import calculate_center
# Import configuration constants
from src.config import (
    MAP_INITIAL_ZOOM,
    MAP_HEIGHT,
    MAP_TILE_URL,
    POLYLINE_SAMPLE_INTERVAL,
    MARKER_MAX_COUNT
)


logger = logging.getLogger(__name__)


class MapView(ft.Container):
    """Interactive map showing the flight path, markers, and statistics."""

    def __init__(self, points: List[FlightPoint], source_file: Path):
        super().__init__()
        self._points = points
        self._source_file = source_file

        # Center of the map
        center_lat, center_lon = calculate_center(self._points)

        # Use config for sampling
        sample_interval_polyline = POLYLINE_SAMPLE_INTERVAL
        sampled_polyline_points = self._points[::sample_interval_polyline]

        # Polyline layer (trajectory)
        polyline_layer = fmap.PolylineLayer(
            polylines=[
                fmap.PolylineMarker(
                    coordinates=[
                        fmap.MapLatitudeLongitude(p.lat, p.lon)
                        for p in sampled_polyline_points
                    ],
                    border_stroke_width=3,
                    border_color=ft.Colors.BLUE,
                    color=ft.Colors.with_opacity(0.6, ft.Colors.BLUE),
                )
            ]
        )

        # Marker sampling for performance
        sample_interval = max(1, len(self._points) // MARKER_MAX_COUNT)
        markers = [
            fmap.Marker(
                content=ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.RED, size=18),
                coordinates=fmap.MapLatitudeLongitude(p.lat, p.lon),
            )
            for p in self._points[::sample_interval]
        ]

        # Start and end markers
        if self._points:
            start = self._points[0]
            end = self._points[-1]
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

        # Create map
        the_map = fmap.Map(
            expand=True,
            initial_center=fmap.MapLatitudeLongitude(center_lat, center_lon),
            initial_zoom=MAP_INITIAL_ZOOM,  # Use config
            height=MAP_HEIGHT,              # Use config
            interaction_configuration=fmap.MapInteractionConfiguration(
                flags=fmap.MapInteractiveFlag.ALL
            ),
            layers=[
                fmap.TileLayer(
                    url_template=MAP_TILE_URL, # Use config
                    # use logging instead of print for tile errors
                    on_image_error=lambda e: logger.error("Tile error: %s", e),
                ),
                polyline_layer,
                fmap.MarkerLayer(markers=markers),
            ],
        )

        # Stats info
        # Guard min/max in case points become empty (defensive)
        if self._points:
            duration = self._points[-1].ts - self._points[0].ts if len(self._points) > 1 else 0
            min_alt = min(p.alt for p in self._points)
            max_alt = max(p.alt for p in self._points)
        else:
            duration = 0
            min_alt = max_alt = 0.0

        stats_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Flight Statistics", size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=1),
                    ft.Text(f"File: {self._source_file.name}", size=12),
                    ft.Text(f"Points: {len(self._points):,}", size=12),
                    ft.Text(f"Duration: {duration:.1f}s", size=12),
                    ft.Text(f"Altitude: {min_alt:.1f}m - {max_alt:.1f}m", size=12),
                ],
                spacing=5,
            ),
            padding=15,
            bgcolor=ft.Colors.ON_SURFACE_VARIANT,
            border_radius=10,
        )

        # Compose the final layout
        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Flight Path", size=24, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        stats_panel,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(the_map, expand=True, border_radius=10),
            ],
            expand=True,
            spacing=15,
        )