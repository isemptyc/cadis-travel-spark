from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .exif import PhotoPoint
from .geo import Bounds


CountryLookup = Callable[[float, float], str | None]
CountryLookupMany = Callable[[list[PhotoPoint]], list[str | None]]

DEFAULT_COUNTRY_LOOKUP_BATCH_SIZE = 50_000


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
    country_lookup_many: CountryLookupMany | None = None,
    country_lookup_batch_size: int = DEFAULT_COUNTRY_LOOKUP_BATCH_SIZE,
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
    require_country_match = expected_country is not None and (country_lookup is not None or country_lookup_many is not None)

    in_bounds: list[PhotoPoint] = []
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

        in_bounds.append(point)

    country_isos: list[str | None] = [None] * len(in_bounds)
    if country_lookup_many is not None and in_bounds:
        batch_size = max(1, int(country_lookup_batch_size))
        total_in_bounds = len(in_bounds)
        for start in range(0, total_in_bounds, batch_size):
            end = min(start + batch_size, total_in_bounds)
            if progress is not None:
                progress("resolving countries with cadis lookup_many", start, total_in_bounds)
            batch = in_bounds[start:end]
            try:
                resolved = country_lookup_many(batch)
            except Exception:
                resolved = []
            if len(resolved) == len(batch):
                country_isos[start:end] = resolved
            if progress is not None:
                progress("resolving countries with cadis lookup_many", end, total_in_bounds)
    elif country_lookup is not None and in_bounds:
        country_cache: dict[tuple[float, float], str | None] = {}
        for index, point in enumerate(in_bounds, start=1):
            if progress is not None and (index == 1 or index == len(in_bounds) or index % 1000 == 0):
                progress("resolving countries with cadis lookup", index, len(in_bounds))
            key = (round(point.latitude, 6), round(point.longitude, 6))
            if key not in country_cache:
                country_cache[key] = country_lookup(point.latitude, point.longitude)
            country_isos[index - 1] = country_cache[key]

    for point, country_iso in zip(in_bounds, country_isos):
        if country_iso:
            detected_countries[country_iso.strip().upper()] += 1
        reason = _skip_reason(
            point,
            bounds=bounds,
            expected_country=expected_country,
            country_iso=country_iso,
            require_country_match=require_country_match,
        )
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
        return _country_iso_from_cadis_result(result)

    return resolve


def cadis_country_lookup_many(
    *,
    allowed_iso2: Iterable[str] | None = None,
    runtime_cache_policy: str | None = "batch",
) -> CountryLookupMany | None:
    try:
        import cadis
    except Exception:
        return None

    lookup_many = getattr(cadis, "lookup_many", None)
    if not callable(lookup_many):
        return None

    normalized_allowed = _normalize_allowed_iso2(allowed_iso2)

    def resolve(points: list[PhotoPoint]) -> list[str | None]:
        rows = [
            {"id": str(index), "lat": point.latitude, "lon": point.longitude}
            for index, point in enumerate(points)
        ]
        try:
            results = _call_cadis_lookup_many(
                lookup_many,
                rows,
                allowed_iso2=normalized_allowed,
                runtime_cache_policy=runtime_cache_policy,
            )
        except Exception:
            return [None] * len(points)
        if not isinstance(results, list) or len(results) != len(points):
            return [None] * len(points)
        return [_country_iso_from_cadis_result(result) for result in results]

    return resolve


def _call_cadis_lookup_many(
    lookup_many: Callable[..., object],
    rows: list[dict[str, object]],
    *,
    allowed_iso2: list[str] | None,
    runtime_cache_policy: str | None,
) -> object:
    kwargs: dict[str, object] = {}
    if allowed_iso2:
        kwargs["allowed_iso2"] = allowed_iso2
    if runtime_cache_policy is not None:
        kwargs["runtime_cache_policy"] = runtime_cache_policy

    attempts: list[dict[str, object]] = [kwargs]
    if "runtime_cache_policy" in kwargs:
        attempts.append({key: value for key, value in kwargs.items() if key != "runtime_cache_policy"})
    if "allowed_iso2" in kwargs:
        attempts.append({key: value for key, value in kwargs.items() if key != "allowed_iso2"})
    attempts.append({})

    seen: set[tuple[str, ...]] = set()
    last_type_error: TypeError | None = None
    for attempt in attempts:
        key = tuple(sorted(attempt))
        if key in seen:
            continue
        seen.add(key)
        try:
            return lookup_many(rows, **attempt)
        except TypeError as exc:
            last_type_error = exc
            continue
    if last_type_error is not None:
        raise last_type_error
    return lookup_many(rows)


def _normalize_allowed_iso2(values: Iterable[str] | None) -> list[str] | None:
    if values is None:
        return None
    normalized = sorted({value.strip().upper() for value in values if isinstance(value, str) and len(value.strip()) == 2})
    return normalized or None


def _country_iso_from_cadis_result(result: Any) -> str | None:
    if isinstance(result, str) and len(result.strip()) == 2:
        return result.strip().upper()
    if isinstance(result, dict):
        for key in ("lookup", "state", "result", "world", "world_context"):
            country = _country_iso_from_cadis_result(result.get(key))
            if country:
                return country
        for key in ("country_iso2", "country_iso", "iso2"):
            value = result.get(key)
            if isinstance(value, str) and len(value.strip()) == 2:
                return value.strip().upper()
        country_value = result.get("country")
        if isinstance(country_value, str) and len(country_value.strip()) == 2:
            return country_value.strip().upper()
        country = _country_iso_from_cadis_result(country_value)
        if country:
            return country
    country = getattr(result, "country_iso2", None) or getattr(result, "country_iso", None) or getattr(result, "iso2", None)
    if isinstance(country, str) and len(country.strip()) == 2:
        return country.strip().upper()
    return None


def _skip_reason(
    point: PhotoPoint,
    *,
    bounds: Bounds,
    expected_country: str | None,
    country_iso: str | None,
    require_country_match: bool = False,
) -> str | None:
    if not bounds.contains(point.latitude, point.longitude):
        return "outside_bounds"
    if require_country_match and expected_country and not country_iso:
        return "country_unresolved"
    if expected_country and country_iso and country_iso.strip().upper() != expected_country:
        return f"country_mismatch:{country_iso.strip().upper()}"
    return None
