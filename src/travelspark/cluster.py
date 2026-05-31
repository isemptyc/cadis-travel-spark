from __future__ import annotations

from dataclasses import dataclass

from .exif import PhotoPoint
from .geo import haversine_km


@dataclass(frozen=True)
class Cluster:
    latitude: float
    longitude: float
    count: int
    members: tuple[PhotoPoint, ...]


def cluster_points(points: list[PhotoPoint], radius_km: float) -> list[Cluster]:
    clusters: list[dict] = []
    for point in points:
        nearest = None
        nearest_distance = float("inf")
        for cluster in clusters:
            distance = haversine_km(point.latitude, point.longitude, cluster["latitude"], cluster["longitude"])
            if distance < nearest_distance:
                nearest = cluster
                nearest_distance = distance
        if nearest is None or nearest_distance > radius_km:
            clusters.append({"latitude": point.latitude, "longitude": point.longitude, "members": [point]})
            continue
        members = nearest["members"]
        count = len(members)
        nearest["latitude"] = (nearest["latitude"] * count + point.latitude) / (count + 1)
        nearest["longitude"] = (nearest["longitude"] * count + point.longitude) / (count + 1)
        members.append(point)
    return [
        Cluster(latitude=row["latitude"], longitude=row["longitude"], count=len(row["members"]), members=tuple(row["members"]))
        for row in clusters
    ]
