from pathlib import Path

import pytest

from travelspark.exif import PhotoPoint
from travelspark.geo import Bounds
from travelspark.scope import filter_points_for_scene


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
    assert result.detected_countries == {"TW": 1, "JP": 1}


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
