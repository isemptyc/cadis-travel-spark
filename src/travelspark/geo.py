from __future__ import annotations

import math
from dataclasses import dataclass


EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Bounds:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def contains(self, lat: float, lon: float) -> bool:
        return self.min_lon <= lon <= self.max_lon and self.min_lat <= lat <= self.max_lat

    def as_dict(self) -> dict[str, float]:
        return {
            "min_lon": self.min_lon,
            "min_lat": self.min_lat,
            "max_lon": self.max_lon,
            "max_lat": self.max_lat,
        }


def bounds_from_values(values: list[float] | tuple[float, float, float, float]) -> Bounds:
    if len(values) != 4:
        raise ValueError(f"bounds must contain four values, got {values!r}")
    return Bounds(float(values[0]), float(values[1]), float(values[2]), float(values[3]))


def project_lonlat(lon: float, lat: float) -> tuple[float, float]:
    clipped = min(85.05112878, max(-85.05112878, lat))
    radians = math.radians(clipped)
    y = math.degrees(math.log(math.tan(math.pi / 4.0 + radians / 2.0)))
    return lon, y


def project_to_pixel(lon: float, lat: float, *, bounds: Bounds, width: int, height: int) -> tuple[float, float]:
    minx, miny = project_lonlat(bounds.min_lon, bounds.min_lat)
    maxx, maxy = project_lonlat(bounds.max_lon, bounds.max_lat)
    x, y = project_lonlat(lon, lat)
    return ((x - minx) / (maxx - minx) * width, (maxy - y) / (maxy - miny) * height)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
