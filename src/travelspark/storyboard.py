from __future__ import annotations

from copy import deepcopy
from typing import Any


STORYBOARD_PRESETS: dict[str, dict[str, Any]] = {
    "spark-drift": {
        "profile": "cadis.travel_spark.storyboard",
        "schema_version": 1,
        "storyboard_id": "spark_drift_v1",
        "description": "Quiet night-sky travel sparks that shimmer softly over the atlas.",
        "output": {
            "format": "gif",
            "fps": 18,
            "frames": 96,
            "loop": True,
        },
        "director": {
            "mode": "ambient-spark",
            "temporal_order": "none",
            "pacing": "quiet",
            "random_seed": 20260601,
        },
        "effects": {
            "spark": {
                "visible_fraction": 0.12,
                "twinkle_period_frames": [72, 168],
                "intensity": [0.04, 0.50],
                "radius_px": [0.8, 2.2],
                "glow_radius_px": [8, 30],
                "blur_px": 5,
                "jitter_px": 0.45,
            },
            "cluster_glow": {
                "enabled": True,
                "opacity": 0.06,
                "radius_px": [24, 56],
                "pulse": 0.04,
            },
        },
    },
}


def load_storyboard_preset(preset_id: str | None) -> dict[str, Any] | None:
    if preset_id is None:
        return None
    preset = STORYBOARD_PRESETS.get(preset_id.strip().lower())
    if preset is None:
        raise ValueError(f"unknown storyboard preset: {preset_id!r}")
    return deepcopy(preset)


def storyboard_mode(preset: dict[str, Any] | None, fallback: str) -> str:
    if preset is None:
        return fallback
    director = preset.get("director")
    if not isinstance(director, dict):
        return fallback
    mode = director.get("mode")
    return str(mode) if isinstance(mode, str) and mode.strip() else fallback
