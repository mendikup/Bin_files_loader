import logging
from pathlib import Path
from typing import List

import flet as ft
import flet_map as fmap

from src.business_logic.models import FlightPoint
from src.business_logic.utils.calculate_center import calculate_center
from src.config.config_loader import load_config

MAP_INITIAL_ZOOM = 13.0
MAP_HEIGHT = 700
MARKER_MAX_COUNT = 400

_MAP_CONFIG = load_config()
MAP_TILE_URL = _MAP_CONFIG["MAP_TILE_URL"]
POLYLINE_SAMPLE_INTERVAL = max(1, int(_MAP_CONFIG["POLYLINE_SAMPLE_INTERVAL"]))


logger = logging.getLogger(__name__)


class MapView(ft.Container):
    """Interactive map that renders the trajectory with contextual details."""

    def __init__(self, points: List[FlightPoint], source_file: Path):
        super().__init__()
        self._points = points
        self._source_file = source_file

        logger.info(
            "Initializing map view for %s with %d points", source_file.name, len(points)
        )

        center_lat, center_lon = calculate_center(self._points)
        logger.debug(
            "Calculated map center for %s: lat=%f, lon=%f",
            source_file.name,
            center_lat,
            center_lon,
        )

        sampled_points = self._points[::POLYLINE_SAMPLE_INTERVAL]
        logger.debug(
            "Sampling %d of %d points for polyline (interval=%d)",
            len(sampled_points),
            len(self._points),
            POLYLINE_SAMPLE_INTERVAL,
        )
        polyline_layer = fmap.PolylineLayer(
            polylines=[
                fmap.PolylineMarker(
                    coordinates=[
                        fmap.MapLatitudeLongitude(point.lat, point.lon)
                        for point in sampled_points
                    ],
                    border_stroke_width=3,
                    border_color=ft.Colors.BLUE,
                    color=ft.Colors.with_opacity(0.6, ft.Colors.BLUE),
                )
            ]
        )

        marker_step = max(1, len(self._points) // MARKER_MAX_COUNT)
        markers = [
            fmap.Marker(
                content=ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.RED, size=18),
                coordinates=fmap.MapLatitudeLongitude(point.lat, point.lon),
            )
            for point in self._points[::marker_step]
        ]

        logger.debug(
            "Plotted %d markers using step=%d (max=%d)",
            len(markers),
            marker_step,
            MARKER_MAX_COUNT,
        )

        if self._points:
            start, end = self._points[0], self._points[-1]
            logger.debug(
                "Start point: lat=%f lon=%f | End point: lat=%f lon=%f",
                start.lat,
                start.lon,
                end.lat,
                end.lon,
            )
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

        flight_map = fmap.Map(
            expand=True,
            initial_center=fmap.MapLatitudeLongitude(center_lat, center_lon),
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

        if self._points:
            duration = self._points[-1].ts - self._points[0].ts if len(self._points) > 1 else 0
            min_alt = min(point.alt for point in self._points)
            max_alt = max(point.alt for point in self._points)
            logger.info(
                "Computed stats for %s: duration=%.1fs, min_alt=%.1fm, max_alt=%.1fm",
                source_file.name,
                duration,
                min_alt,
                max_alt,
            )
        else:
            duration = 0.0
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
                ft.Container(flight_map, expand=True, border_radius=10),
            ],
            expand=True,
            spacing=15,
        )
