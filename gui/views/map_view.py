from __future__ import annotations
from typing import List
import flet as ft
import flet_map as map

from business_logic.models import FlightPoint
from gui.state import STATE


def _polyline_layer(points: List[FlightPoint]) -> map.PolylineLayer:
    """שכבת קו בין נקודות המסלול (עם ניקוי ודילול)"""
    if not points:
        return map.PolylineLayer(polylines=[])

    # ✅ סינון לפי טווח ישראל כדי להסיר נקודות חריגות שמקפיצות לים
    filtered = [p for p in points if 29 < p.lat < 34.8 and 33 < p.lon < 36]
    print(f"[DEBUG] סוננו {len(points) - len(filtered)} נקודות חריגות")

    # ✅ דילול נקודות לציור מהיר יותר
    simplified = filtered[::50]  # כל 50 נקודות מספיקות לייצוג קו רציף
    print(f"[DEBUG] נבחרו {len(simplified)} נקודות לציור הקו")

    return map.PolylineLayer(
        polylines=[
            map.PolylineMarker(
                coordinates=[
                    map.MapLatitudeLongitude(p.lat, p.lon) for p in simplified
                ],
                color=ft.Colors.BLUE,          # 💙 קו כחול במקום אדום
                border_stroke_width=2,         # קו דק יותר
            )
        ]
    )


class MapView(ft.Container):
    """תצוגת מפה המציגה את נתיב הטיסה"""

    def __init__(self):
        super().__init__()

        # 🧭 שליפת הנקודות ממדינת האפליקציה
        points = STATE.points or []

        if not points:
            print("[DEBUG] ⚠️ STATE.points ריק — לא הוזנו נקודות למפה")
            self.content = ft.Text("לא נמצאו נתוני טיסה להצגה.")
            return

        print(f"[DEBUG] ✅ נטענו {len(points)} נקודות למפה")

        center_lat = points[0].lat
        center_lon = points[0].lon
        print(f"[DEBUG] 🗺️ מרכז המפה: lat={center_lat}, lon={center_lon}")
        print(f"[DEBUG] 📍 דוגמה לנקודה: {points[0].lat}, {points[0].lon}")

        # 🔵 סמנים מדוללים בלבד כדי לשמור על ביצועים
        markers = [
            map.Marker(
                content=ft.Container(bgcolor="blue", width=5, height=5, border_radius=2),
                coordinates=map.MapLatitudeLongitude(p.lat, p.lon),
            )
            for p in points[:: max(1, len(points) // 150)]
        ]
        print(f"[DEBUG] 📍 נוצרו {len(markers)} סמנים למפה")

        # 🗺️ יצירת המפה
        the_map = map.Map(
            expand=True,
            initial_center=map.MapLatitudeLongitude(center_lat, center_lon),
            initial_zoom=12,  # 🔍 זום רחוק יותר לתצוגה מלאה
            interaction_configuration=map.MapInteractionConfiguration(
                flags=map.MapInteractiveFlag.ALL
            ),
            layers=[
                map.TileLayer(
                    url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                    on_image_error=lambda e: print("❌ Tile error:", e),
                ),
                _polyline_layer(points),
                map.MarkerLayer(markers=markers),
            ],
        )

        # ✅ גובה קבוע + רקע שקוף לבדיקה
        self.content = ft.Column(
            [
                ft.Text("נתיב הטיסה", size=22, weight=ft.FontWeight.BOLD),
                ft.Container(
                    the_map,
                    expand=True,
                    height=700,  # גובה קבוע למניעת העלמות
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
                ),
            ],
            expand=True,
        )
