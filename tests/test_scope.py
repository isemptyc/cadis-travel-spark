import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from travelspark.exif import PhotoPoint
from travelspark.geo import Bounds
from travelspark.scope import (
    DEFAULT_COUNTRY_LOOKUP_BATCH_SIZE,
    _country_iso_from_cadis_result,
    cadis_country_lookup_many,
    filter_points_for_scene,
)


def test_filter_points_for_single_country_scene_skips_mismatches():
    tw_point = PhotoPoint(Path("tw.jpg"), 25.0, 121.5)
    jp_point = PhotoPoint(Path("jp.jpg"), 35.0, 139.7)

    result = filter_points_for_scene(
        [tw_point, jp_point],
        bounds=Bounds(118.0, 20.0, 123.5, 26.8),
        scene_country_iso="TW",
        country_lookup=lambda lat, lon: "TW" if lon < 130 else "JP",
    )

    assert result.kept == [tw_point]
    assert result.skipped == [jp_point]
    assert result.skipped_reasons == {"outside_bounds": 1}
    # Outside-bounds points are skipped before the expensive country lookup.
    assert result.detected_countries == {"TW": 1}


def test_strict_scope_policy_fails_on_skipped_points():
    with pytest.raises(ValueError, match="outside selected scene scope"):
        filter_points_for_scene(
            [PhotoPoint(Path("jp.jpg"), 35.0, 139.7)],
            bounds=Bounds(118.0, 20.0, 123.5, 26.8),
            scene_country_iso="TW",
            policy="strict",
        )


def test_filter_policy_fails_only_when_no_points_remain():
    with pytest.raises(ValueError, match="no GPS points remain"):
        filter_points_for_scene(
            [PhotoPoint(Path("jp.jpg"), 35.0, 139.7)],
            bounds=Bounds(118.0, 20.0, 123.5, 26.8),
            scene_country_iso="TW",
        )


def test_country_lookup_is_not_called_for_outside_bounds_points():
    inside = PhotoPoint(Path("tw.jpg"), 25.0, 121.5)
    outside = PhotoPoint(Path("jp.jpg"), 35.0, 139.7)
    calls = []

    def lookup(lat: float, lon: float) -> str:
        calls.append((lat, lon))
        return "TW"

    result = filter_points_for_scene(
        [inside, outside],
        bounds=Bounds(118.0, 20.0, 123.5, 26.8),
        scene_country_iso="TW",
        country_lookup=lookup,
    )

    assert result.kept == [inside]
    assert result.skipped == [outside]
    assert calls == [(25.0, 121.5)]


def test_batch_country_lookup_receives_only_in_bounds_points():
    tw_point = PhotoPoint(Path("tw.jpg"), 25.0, 121.5)
    misclassified_point = PhotoPoint(Path("misclassified.jpg"), 24.0, 120.5)
    outside = PhotoPoint(Path("jp.jpg"), 35.0, 139.7)
    calls = []

    def lookup_many(batch: list[PhotoPoint]) -> list[str | None]:
        calls.append(batch)
        return ["TW", "JP"]

    result = filter_points_for_scene(
        [tw_point, misclassified_point, outside],
        bounds=Bounds(118.0, 20.0, 123.5, 26.8),
        scene_country_iso="TW",
        country_lookup_many=lookup_many,
    )

    assert calls == [[tw_point, misclassified_point]]
    assert result.kept == [tw_point]
    assert result.skipped == [outside, misclassified_point]
    assert result.skipped_reasons == {"outside_bounds": 1, "country_mismatch:JP": 1}
    assert result.detected_countries == {"TW": 1, "JP": 1}


def test_active_country_lookup_requires_resolved_country_match():
    tw_point = PhotoPoint(Path("tw.jpg"), 25.0, 121.5)
    unresolved_point = PhotoPoint(Path("okinawa.jpg"), 26.2, 127.7)

    result = filter_points_for_scene(
        [tw_point, unresolved_point],
        bounds=Bounds(116.0, 20.0, 132.0, 36.0),
        scene_country_iso="TW",
        country_lookup_many=lambda batch: ["TW", None],
    )

    assert result.kept == [tw_point]
    assert result.skipped == [unresolved_point]
    assert result.skipped_reasons == {"country_unresolved": 1}
    assert result.detected_countries == {"TW": 1}


def test_batch_country_lookup_uses_bounded_cadis_batches():
    points = [PhotoPoint(Path(f"tw-{index}.jpg"), 25.0 + index * 0.001, 121.5) for index in range(5)]
    calls = []

    def lookup_many(batch: list[PhotoPoint]) -> list[str | None]:
        calls.append([point.path.name for point in batch])
        return ["TW"] * len(batch)

    result = filter_points_for_scene(
        points,
        bounds=Bounds(118.0, 20.0, 123.5, 26.8),
        scene_country_iso="TW",
        country_lookup_many=lookup_many,
        country_lookup_batch_size=2,
    )

    assert result.kept == points
    assert calls == [["tw-0.jpg", "tw-1.jpg"], ["tw-2.jpg", "tw-3.jpg"], ["tw-4.jpg"]]
    assert DEFAULT_COUNTRY_LOOKUP_BATCH_SIZE == 50_000


def test_cadis_country_lookup_many_uses_public_batch_contract(monkeypatch):
    point = PhotoPoint(Path("tw.jpg"), 25.0, 121.5)
    calls = {}

    def lookup_many(points, **kwargs):
        calls["points"] = points
        calls["kwargs"] = kwargs
        return [
            {
                "id": points[0]["id"],
                "lookup": {
                    "state": {"world": {"status": "ok", "classification": "country", "iso2": "tw"}},
                    "result": None,
                },
            }
        ]

    monkeypatch.setitem(sys.modules, "cadis", SimpleNamespace(lookup_many=lookup_many))

    resolve = cadis_country_lookup_many(allowed_iso2=["tw"])

    assert resolve is not None
    assert resolve([point]) == ["TW"]
    assert calls["points"] == [{"id": "0", "lat": 25.0, "lon": 121.5}]
    assert calls["kwargs"] == {"allowed_iso2": ["TW"], "runtime_cache_policy": "batch"}


def test_cadis_country_lookup_many_maps_results_by_returned_id(monkeypatch):
    tw_point = PhotoPoint(Path("tw.jpg"), 25.0, 121.5)
    jp_point = PhotoPoint(Path("jp.jpg"), 35.0, 139.7)

    def lookup_many(points, **kwargs):
        return [
            {
                "id": points[1]["id"],
                "lookup": {"state": {"world": {"iso2": "JP"}}},
            },
            {
                "id": points[0]["id"],
                "lookup": {"state": {"world": {"iso2": "TW"}}},
            },
        ]

    monkeypatch.setitem(sys.modules, "cadis", SimpleNamespace(lookup_many=lookup_many))

    resolve = cadis_country_lookup_many()

    assert resolve is not None
    assert resolve([tw_point, jp_point]) == ["TW", "JP"]


def test_country_iso_parser_handles_lookup_many_payloads():
    assert _country_iso_from_cadis_result({"lookup": {"state": {"world": {"iso2": "tw"}}}}) == "TW"
    assert _country_iso_from_cadis_result({"lookup": {"result": {"country_iso2": "jp"}}}) == "JP"
    assert _country_iso_from_cadis_result({"world_context": {"country": {"iso2": "fr"}}}) == "FR"
