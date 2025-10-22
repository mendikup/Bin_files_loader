import flet as ft
import flet_map as fmap
from pathlib import Path
from typing import List, Tuple

from src.utils.logger import logger
from src.utils.config_loader import config
from src.business_logic.models import FlightPoint


class MapView(ft.Container):
    """Displays an interactive map with the loaded flight path."""

    def __init__(self, points: List[FlightPoint], source_file: Path):
        super().__init__()
        self._points = points
        self._source_file = source_file

        lat, lon = self._get_center()
        polyline_layer = self._build_polyline_layer()
        markers = self._build_markers()
        fmap_component = self._create_map(lat, lon, polyline_layer, markers)
        stats_panel = self._build_stats_panel()
        self.content = self._layout(fmap_component, stats_panel)

    def _get_center(self) -> Tuple[float, float]:
        if not self._points:
            return 0.0, 0.0
        lat = sum(p.lat for p in self._points) / len(self._points)
        lon = sum(p.lon for p in self._points) / len(self._points)
        return lat, lon

    def _build_polyline_layer(self) -> fmap.PolylineLayer:
        interval = config.map.polyline_sample_interval
        sampled_points = self._points[::interval]
        polyline = fmap.PolylineMarker(
            coordinates=[fmap.MapLatitudeLongitude(p.lat, p.lon) for p in sampled_points],
            border_stroke_width=3,
            border_color=ft.Colors.BLUE,
            color=ft.Colors.with_opacity(0.6, ft.Colors.BLUE),
        )
        return fmap.PolylineLayer(polylines=[polyline])

    def _build_markers(self) -> List[fmap.Marker]:
        max_count = config.map.marker_max_count
        step = max(1, len(self._points) // max_count)
        markers = [
            fmap.Marker(
                content=ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.RED, size=18),
                coordinates=fmap.MapLatitudeLongitude(p.lat, p.lon),
            )
            for p in self._points[::step]
        ]
        if self._points:
            start, end = self._points[0], self._points[-1]
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
        return markers

    def _create_map(self, lat: float, lon: float, polyline_layer: fmap.PolylineLayer, markers: List[fmap.Marker]) -> fmap.Map:
        return fmap.Map(
            expand=True,
            initial_center=fmap.MapLatitudeLongitude(lat, lon),
            initial_zoom=config.map.initial_zoom,
            height=config.map.height,
            layers=[
                fmap.TileLayer(url_template=config.map.tile_url),
                polyline_layer,
                fmap.MarkerLayer(markers=markers),
            ],
        )

    def _build_stats_panel(self) -> ft.Container:
        if not self._points:
            return ft.Container(content=ft.Text("No data"))
        duration = self._points[-1].ts - self._points[0].ts
        min_alt = min(p.alt for p in self._points)
        max_alt = max(p.alt for p in self._points)
        stats = [
            ft.Text(f"File: {self._source_file.name}"),
            ft.Text(f"Points: {len(self._points):,}"),
            ft.Text(f"Duration: {duration:.1f}s"),
            ft.Text(f"Altitude: {min_alt:.1f}m - {max_alt:.1f}m"),
        ]
        return ft.Container(content=ft.Column(stats, spacing=4), padding=10)

    def _layout(self, fmap_component: fmap.Map, stats_panel: ft.Container) -> ft.Column:
        header = ft.Row(
            [ft.Text("Flight Path", size=22, weight=ft.FontWeight.BOLD), stats_panel],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        return ft.Column([header, ft.Container(fmap_component, expand=True, border_radius=10)], expand=True)
