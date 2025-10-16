from pathlib import Path
from typing import List
import flet as ft
import flet_map as map

from src.business_logic.models import FlightPoint
from src.business_logic.services import calculate_center


class MapView(ft.Container):
    """Interactive map showing flight path with trajectory and markers."""

    def __init__(self, points: List[FlightPoint], source_file: Path):
        super().__init__()
        self._points = points
        self._source_file = source_file



        # Center of the map
        center_lat, center_lon = calculate_center(self._points)

        sampled_polyline_points = self._points[::10]

        # Polyline layer (trajectory)
        polyline_layer = map.PolylineLayer(
            polylines=[
                map.PolylineMarker(
                    coordinates=[
                        map.MapLatitudeLongitude(p.lat, p.lon)
                        for p in sampled_polyline_points                    ],
                    border_stroke_width=3,
                    border_color=ft.Colors.BLUE,
                    color=ft.Colors.with_opacity(0.6, ft.Colors.BLUE),
                )
            ]
        )

        # Marker sampling for performance
        sample_interval = max(1, len(self._points) // 400)
        markers = [
            map.Marker(
                content=ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.RED, size=18),
                coordinates=map.MapLatitudeLongitude(p.lat, p.lon),
            )
            for p in self._points[::sample_interval]
        ]

        # Start and end markers
        if self._points:
            start = self._points[0]
            end = self._points[-1]
            markers.insert(
                0,
                map.Marker(
                    content=ft.Icon(ft.Icons.FLIGHT_TAKEOFF, color=ft.Colors.GREEN, size=24),
                    coordinates=map.MapLatitudeLongitude(start.lat, start.lon),
                ),
            )
            markers.append(
                map.Marker(
                    content=ft.Icon(ft.Icons.FLIGHT_LAND, color=ft.Colors.ORANGE, size=24),
                    coordinates=map.MapLatitudeLongitude(end.lat, end.lon),
                )
            )

        # Create map
        the_map = map.Map(
            expand=True,
            initial_center=map.MapLatitudeLongitude(center_lat, center_lon),
            initial_zoom=13.0,
            height=700,
            interaction_configuration=map.MapInteractionConfiguration(
                flags=map.MapInteractiveFlag.ALL
            ),
            layers=[
                map.TileLayer(
                    url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                    on_image_error=lambda e: print("Tile error:", e),
                ),
                polyline_layer,
                map.MarkerLayer(markers=markers),
            ],
        )

        # Stats info
        duration = self._points[-1].ts - self._points[0].ts if len(self._points) > 1 else 0
        min_alt = min(p.alt for p in self._points)
        max_alt = max(p.alt for p in self._points)

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
            bgcolor=ft.Colors.ON_SURFACE_VARIANT,  # ← כאן התיקון
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
