from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable

from .exif import PhotoPoint
from .geo import Bounds


CountryLookup = Callable[[float, float], str | None]


@dataclass(frozen=True)
class ScopeResult:
    kept: list[PhotoPoint]
    skipped: list[PhotoPoint]
    skipped_reasons: dict[str, int]
    detected_countries: dict[str, int]


def filter_points_for_scene(
    points: list[PhotoPoint],
    *,
    bounds: Bounds,
    scene_country_iso: str | None = None,
    policy: str = "filter",
    country_lookup: CountryLookup | None = None,
    progress: Callable[[str, int, int], None] | None = None,
) -> ScopeResult:
    if policy not in {"filter", "strict", "none"}:
        raise ValueError("scope policy must be filter, strict, or none")
    if policy == "none":
        return ScopeResult(kept=list(points), skipped=[], skipped_reasons={}, detected_countries={})

    kept: list[PhotoPoint] = []
    skipped: list[PhotoPoint] = []
    skipped_reasons: Counter[str] = Counter()
    detected_countries: Counter[str] = Counter()
    expected_country = scene_country_iso.strip().upper() if isinstance(scene_country_iso, str) and scene_country_iso.strip() else None

    country_cache: dict[tuple[float, float], str | None] = {}
    total = len(points)
    for index, point in enumerate(points, start=1):
        if progress is not None and (index == 1 or index == total or index % 1000 == 0):
            progress("filtering points for scene scope", index, total)

        # Bounds checks are cheap and remove most irrelevant photos for country
        # scenes.  Do them before the optional CADIS country lookup, which can
        # be expensive on large global photo libraries.
        if not bounds.contains(point.latitude, point.longitude):
            skipped.append(point)
            skipped_reasons["outside_bounds"] += 1
            continue

        country_iso = None
        if country_lookup is not None:
            key = (round(point.latitude, 6), round(point.longitude, 6))
            if key not in country_cache:
                country_cache[key] = country_lookup(point.latitude, point.longitude)
            country_iso = country_cache[key]
        if country_iso:
            detected_countries[country_iso.strip().upper()] += 1
        reason = _skip_reason(point, bounds=bounds, expected_country=expected_country, country_iso=country_iso)
        if reason is None:
            kept.append(point)
        else:
            skipped.append(point)
            skipped_reasons[reason] += 1

    if skipped and policy == "strict":
        raise ValueError(f"{len(skipped)} point(s) are outside selected scene scope: {dict(skipped_reasons)}")
    if not kept:
        raise ValueError("no GPS points remain after scene-scope filtering")
    return ScopeResult(
        kept=kept,
        skipped=skipped,
        skipped_reasons=dict(skipped_reasons),
        detected_countries=dict(detected_countries),
    )


def cadis_country_lookup() -> CountryLookup | None:
    try:
        import cadis
    except Exception:
        return None

    lookup = getattr(cadis, "lookup", None)
    if not callable(lookup):
        return None

    def resolve(lat: float, lon: float) -> str | None:
        try:
            result = lookup(lat, lon)
        except Exception:
            return None
        if isinstance(result, str) and len(result.strip()) == 2:
            return result.strip().upper()
        if isinstance(result, dict):
            for key in ("country_iso2", "country_iso", "iso2", "country"):
                value = result.get(key)
                if isinstance(value, str) and len(value.strip()) == 2:
                    return value.strip().upper()
        country = getattr(result, "country_iso2", None) or getattr(result, "country_iso", None) or getattr(result, "iso2", None)
        if isinstance(country, str) and len(country.strip()) == 2:
            return country.strip().upper()
        return None

    return resolve


def _skip_reason(
    point: PhotoPoint,
    *,
    bounds: Bounds,
    expected_country: str | None,
    country_iso: str | None,
) -> str | None:
    if not bounds.contains(point.latitude, point.longitude):
        return "outside_bounds"
    if expected_country and country_iso and country_iso.strip().upper() != expected_country:
        return f"country_mismatch:{country_iso.strip().upper()}"
    return None
