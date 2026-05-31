from pathlib import Path

from PIL import Image

from travelspark.animation import render_gif, render_still
from travelspark.exif import PhotoPoint
from travelspark.geo import Bounds
from travelspark.style import DEFAULT_SPARK_STYLE


def test_render_gif_writes_file(tmp_path: Path):
    points = [
        PhotoPoint(tmp_path / "a.jpg", 25.04, 121.56),
        PhotoPoint(tmp_path / "b.jpg", 25.05, 121.57),
    ]
    output = tmp_path / "render.gif"

    report = render_gif(
        points,
        output,
        bounds=Bounds(120.5, 24.4, 122.3, 25.6),
        style=DEFAULT_SPARK_STYLE,
        base_map=Image.new("RGB", (320, 240), (7, 18, 31)),
        width=320,
        height=240,
        frames=6,
        fps=6,
    )

    assert output.is_file()
    assert report["point_count"] == 2


def test_render_gif_writes_ambient_spark_file(tmp_path: Path):
    points = [
        PhotoPoint(tmp_path / "a.jpg", 25.04, 121.56),
        PhotoPoint(tmp_path / "b.jpg", 25.05, 121.57),
    ]
    output = tmp_path / "ambient.gif"

    report = render_gif(
        points,
        output,
        bounds=Bounds(120.5, 24.4, 122.3, 25.6),
        style=DEFAULT_SPARK_STYLE,
        base_map=Image.new("RGB", (320, 240), (7, 18, 31)),
        width=320,
        height=240,
        mode="ambient-spark",
        frames=6,
        fps=6,
    )

    assert output.is_file()
    assert report["storyboard"] == "ambient-spark"
    assert report["point_count"] == 2


def test_render_still_writes_jpeg_without_effect(tmp_path: Path):
    points = [
        PhotoPoint(tmp_path / "a.jpg", 25.04, 121.56),
        PhotoPoint(tmp_path / "b.jpg", 25.05, 121.57),
    ]
    output = tmp_path / "render.jpg"

    report = render_still(
        points,
        output,
        bounds=Bounds(120.5, 24.4, 122.3, 25.6),
        style=DEFAULT_SPARK_STYLE,
        base_map=Image.new("RGB", (320, 240), (7, 18, 31)),
        width=320,
        height=240,
        effect="none",
    )

    assert output.is_file()
    assert report["output_format"] == "jpeg"
    assert report["storyboard"] == "all-points"
    assert report["effect"] == "none"
