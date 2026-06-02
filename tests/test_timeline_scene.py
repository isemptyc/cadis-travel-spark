from pathlib import Path
import json

from PIL import Image

from travelspark.engine import BaseMap
from travelspark.exif import PhotoPoint
from travelspark.geo import bounds_from_values
from travelspark.style import load_style
from travelspark.timeline_scene import write_timeline_scene_package
from travelspark.cli import _aspect_preserving_size


def test_aspect_preserving_size_contains_world_map_in_requested_viewport():
    assert _aspect_preserving_size(8192, 4096, 1280, 720) == (1280, 640)
    assert _aspect_preserving_size(4096, 4096, 1280, 720) == (720, 720)


def test_write_timeline_scene_package_exports_json_assets_and_player(tmp_path: Path):
    base_map = BaseMap(
        image=Image.new("RGB", (320, 180), (4, 9, 16)),
        bounds=bounds_from_values([120, 20, 122, 26]),
        scene_id="tw",
        scene_version="0.1.20",
        metadata={"source": "test"},
    )
    report = write_timeline_scene_package(
        scene_json=tmp_path / "timeline-scene.json",
        points=[
            PhotoPoint(tmp_path / "a.jpg", 25.04, 121.56),
            PhotoPoint(tmp_path / "b.jpg", 25.041, 121.561),
        ],
        base_map=base_map,
        style=load_style(None, style_id="spark-night"),
        storyboard="ambient-spark",
        storyboard_preset="spark-drift",
        width=320,
        height=180,
        frames=96,
        fps=18,
        cluster_radius_km=8.0,
        player_html=tmp_path / "player.html",
    )

    scene_json = tmp_path / "timeline-scene.json"
    assert scene_json.is_file()
    assert (tmp_path / "timeline-scene_assets" / "basemap.png").is_file()
    assert (tmp_path / "player.html").is_file()
    scene_text = scene_json.read_text(encoding="utf-8")
    player_text = (tmp_path / "player.html").read_text(encoding="utf-8")
    assert '"profile": "cadis.travel_spark.timeline_scene"' in scene_text
    assert '"type": "ambient-spark"' in scene_text
    assert '"source_point_count": 2' in scene_text
    assert '"spark_site_count": 1' in scene_text
    assert "timeline-scene_assets/basemap.png" in player_text
    assert "16 / 9" not in player_text
    assert "resizeCanvasElement" in player_text
    assert report["timeline_scene_json"] == str(scene_json)


def test_timeline_scene_spark_periods_are_loop_aligned(tmp_path: Path):
    base_map = BaseMap(
        image=Image.new("RGB", (320, 180), (4, 9, 16)),
        bounds=bounds_from_values([120, 20, 122, 26]),
        scene_id="tw",
        scene_version="0.1.20",
        metadata={"source": "test"},
    )

    write_timeline_scene_package(
        scene_json=tmp_path / "timeline-scene.json",
        points=[
            PhotoPoint(tmp_path / "a.jpg", 25.04, 121.56),
            PhotoPoint(tmp_path / "b.jpg", 25.2, 121.8),
        ],
        base_map=base_map,
        style=load_style(None, style_id="spark-night"),
        storyboard="ambient-spark",
        storyboard_preset="spark-drift",
        width=320,
        height=180,
        frames=96,
        fps=18,
        cluster_radius_km=1.0,
        player_html=tmp_path / "player.html",
    )

    scene = json.loads((tmp_path / "timeline-scene.json").read_text(encoding="utf-8"))
    duration = scene["timing"]["duration_ms"]
    points = scene["effects"]["points"]

    assert points
    for point in points:
        assert point["loop_cycles"] in {1, 2}
        assert point["period_ms"] * point["loop_cycles"] == duration
