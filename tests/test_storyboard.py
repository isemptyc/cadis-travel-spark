from travelspark.storyboard import load_storyboard_preset, storyboard_mode


def test_spark_drift_preset_selects_ambient_spark_storyboard():
    preset = load_storyboard_preset("spark-drift")

    assert preset is not None
    assert preset["storyboard_id"] == "spark_drift_v1"
    assert storyboard_mode(preset, "all-points") == "ambient-spark"
    assert preset["output"]["format"] == "gif"
    assert preset["effects"]["spark"]["twinkle_period_frames"] == [72, 168]
    assert preset["effects"]["spark"]["radius_px"] == [0.8, 2.2]
    assert preset["effects"]["cluster_glow"]["opacity"] == 0.06
