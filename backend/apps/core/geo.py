"""Small geographic helpers shared by incident visibility and alert fan-out."""

import math

from django.db.models import Q

_METRES_PER_DEGREE = 111_320.0


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in metres between two points."""
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    d_phi = phi2 - phi1
    d_lam = math.radians(float(lon2) - float(lon1))
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def bounding_box(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """``(min_lat, max_lat, min_lon, max_lon)`` of the square enclosing the circle."""
    lat_delta = radius_m / _METRES_PER_DEGREE
    lon_delta = radius_m / (_METRES_PER_DEGREE * max(math.cos(math.radians(lat)), 1e-6))
    return lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta


def box_q(lat_field: str, lon_field: str, lat: float, lon: float, radius_m: float) -> Q:
    """Q matching rows whose coordinates fall inside the bounding box of the circle."""
    min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, radius_m)
    return Q(
        **{
            f"{lat_field}__gte": min_lat,
            f"{lat_field}__lte": max_lat,
            f"{lon_field}__gte": min_lon,
            f"{lon_field}__lte": max_lon,
        }
    )


def in_box(lat, lon, centre_lat, centre_lon, radius_m: float) -> bool:
    """Python twin of :func:`box_q`, so list and detail visibility always agree."""
    min_lat, max_lat, min_lon, max_lon = bounding_box(float(centre_lat), float(centre_lon), radius_m)
    return min_lat <= float(lat) <= max_lat and min_lon <= float(lon) <= max_lon
