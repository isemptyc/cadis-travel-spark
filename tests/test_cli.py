from pathlib import Path

from travelspark.cli import _presentation_targets


def test_spark_drift_defaults_to_timeline_scene_without_gif():
    output, export_scene = _presentation_targets(
        output=None,
        export_scene=None,
        storyboard="ambient-spark",
        storyboard_preset="spark-drift",
    )

    assert output is None
    assert export_scene == Path("timeline-scene.json")


def test_all_points_still_defaults_to_jpeg():
    output, export_scene = _presentation_targets(
        output=None,
        export_scene=None,
        storyboard="all-points",
        storyboard_preset=None,
    )

    assert output == Path("travel.jpg")
    assert export_scene is None


def test_explicit_spark_drift_gif_output_is_respected():
    output, export_scene = _presentation_targets(
        output=Path("travel.gif"),
        export_scene=None,
        storyboard="ambient-spark",
        storyboard_preset="spark-drift",
    )

    assert output == Path("travel.gif")
    assert export_scene is None
