from __future__ import annotations

from typing import List

import flet as ft
import flet.map as ftm

from business_logic.models import FlightPoint
from gui.state import STATE


def _polyline_layer(points: List[FlightPoint]) -> ftm.PolylineLayer:
    if not points:
        return ftm.PolylineLayer(polylines=[])
    return ftm.PolylineLayer(
        polylines=[
            ftm.PolylineMarker(
                coordinates=[ftm.MapLatitudeLongitude(p.lat, p.lon) for p in points]
            )
        ]
    )


class MapView(ft.Container):
    """Display the loaded coordinates on top of OpenStreetMap tiles."""

    def __init__(self):
        super().__init__()

        points = STATE.points or []
        center_lat = points[0].lat if points else 0
        center_lon = points[0].lon if points else 0

        markers = [
            ftm.Marker(
                content=ft.Container(bgcolor="red", width=6, height=6, border_radius=3),
                coordinates=ftm.MapLatitudeLongitude(p.lat, p.lon),
            )
            for p in points[:: max(1, len(points) // 200)]
        ]

        the_map = ftm.Map(
            expand=True,
            initial_center=ftm.MapLatitudeLongitude(center_lat, center_lon),
            initial_zoom=12,
            layers=[
                ftm.TileLayer(url_template="https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"),
                _polyline_layer(points),
                ftm.MarkerLayer(markers=markers),
            ],
        )

        self.content = ft.Column(
            [
                ft.Text("נתיב הטיסה", size=22, weight=ft.FontWeight.BOLD),
                ft.Container(the_map, expand=True),
            ],
            expand=True,
        )
