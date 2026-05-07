import os
import io
import math
import logging
import requests
from typing import List, Dict
from PIL import Image

logger = logging.getLogger(__name__)

# Esri World Imagery — free, no API key, high-res satellite tiles
ESRI_EXPORT_URL = (
    "https://services.arcgisonline.com/ArcGIS/rest/services"
    "/World_Imagery/MapServer/export"
)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_HEADERS = {"User-Agent": "BlueCarbonRegistry/1.0"}


def calculate_area_hectares(coords: List[Dict]) -> float:
    """Spherical excess formula — returns area in hectares."""
    n = len(coords)
    if n < 3:
        return 0.0
    R = 6371000.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        lat1 = math.radians(coords[i]["lat"])
        lng1 = math.radians(coords[i]["lng"])
        lat2 = math.radians(coords[j]["lat"])
        lng2 = math.radians(coords[j]["lng"])
        area += (lng2 - lng1) * (2 + math.sin(lat1) + math.sin(lat2))
    return abs(area) * R * R / 2 / 10000


def get_polygon_center(coords: List[Dict]) -> Dict:
    return {
        "lat": sum(c["lat"] for c in coords) / len(coords),
        "lng": sum(c["lng"] for c in coords) / len(coords),
    }


def fetch_satellite_image(coords: List[Dict], area_hectares: float) -> bytes:
    """
    Fetch a satellite image of the polygon bounding box from
    Esri World Imagery (free, no API key needed).
    """
    lats = [c["lat"] for c in coords]
    lngs = [c["lng"] for c in coords]

    # Expand bounding box by 10% for context
    lat_pad = (max(lats) - min(lats)) * 0.1 or 0.005
    lng_pad = (max(lngs) - min(lngs)) * 0.1 or 0.005

    min_lng = min(lngs) - lng_pad
    min_lat = min(lats) - lat_pad
    max_lng = max(lngs) + lng_pad
    max_lat = max(lats) + lat_pad

    params = {
        "bbox": f"{min_lng},{min_lat},{max_lng},{max_lat}",
        "bboxSR": "4326",
        "imageSR": "4326",
        "size": "640,640",
        "format": "jpg",
        "f": "image",
    }

    logger.info(f"Fetching Esri satellite image for bbox {params['bbox']}")
    resp = requests.get(ESRI_EXPORT_URL, params=params, timeout=20)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if "image" not in content_type:
        raise ValueError(
            f"Esri returned unexpected content-type: {content_type}. "
            "Check your coordinates."
        )

    return resp.content


def reverse_geocode(lat: float, lng: float) -> str:
    """
    Reverse-geocode coordinates to a place name using Nominatim
    (OpenStreetMap) — free, no API key needed.
    """
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"lat": lat, "lon": lng, "format": "json", "zoom": 10},
            headers=NOMINATIM_HEADERS,
            timeout=8,
        )
        data = resp.json()
        addr = data.get("address", {})
        name = (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("county")
            or addr.get("state")
            or data.get("display_name", "").split(",")[0]
        )
        return name or f"Site {lat:.4f}N"
    except Exception as e:
        logger.warning(f"Nominatim geocoding failed: {e}")
        return f"Coastal Site {lat:.4f}N {abs(lng):.4f}{'E' if lng >= 0 else 'W'}"
