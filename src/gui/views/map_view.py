from __future__ import annotations
from typing import List

import flet as ft
import flet.map as ftm

from drone_flet_basic.src.business_logic.models import FlightPoint
from drone_flet_basic.src.gui.state import STATE


def _polyline_layer(points: List[FlightPoint]) -> ftm.PolylineLayer:
    if not points:
        return ftm.PolylineLayer(polylines=[])
    return ftm.PolylineLayer(
        polylines=[
            ftm.PolylineMarker(
                coordinates=[
                    ftm.MapLatitudeLongitude(p.lat, p.lon) for p in points
                ]
            )
        ]
    )


class MapView(ft.Container):
    """Display the flight path on OpenStreetMap tiles using Flet 0.27.3."""

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

        marker_layer = ftm.MarkerLayer(markers=markers)

        the_map = ftm.Map(
            expand=True,
            layers=[
                ftm.TileLayer(
                    url_template="https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
                ),
                _polyline_layer(points),
                marker_layer,
            ],
        )

        # 🔹 הגדרה של זום ומרכז
        the_map.initial_center = ftm.MapLatitudeLongitude(center_lat, center_lon)
        the_map.initial_zoom = 12

        self.content = ft.Column(
            [
                ft.Text("Flight Path", size=22, weight=ft.FontWeight.BOLD),
                ft.Container(the_map, expand=True),
            ],
            expand=True,
        )
