from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SPARK_STYLE: dict[str, Any] = {
    "base": {
        "sea": [5, 14, 25],
        "land": [33, 65, 50],
        "inner_border": [45, 75, 66],
    },
    "activation": {
        "glow_color": [255, 209, 96],
        "marker_color": [255, 239, 166],
        "marker_outline_color": [79, 61, 20],
        "min_glow_radius_px": 26,
        "max_glow_radius_px": 86,
    },
}


def load_style(path: Path | None) -> dict[str, Any]:
    if path is None:
        return DEFAULT_SPARK_STYLE
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"style must be a JSON object: {path}")
    return _deep_merge(DEFAULT_SPARK_STYLE, payload)


def color(style: dict[str, Any], section: str, key: str) -> tuple[int, int, int]:
    value = style.get(section, {}).get(key, DEFAULT_SPARK_STYLE[section][key])
    if not isinstance(value, list | tuple) or len(value) < 3:
        raise ValueError(f"style color {section}.{key} must be an RGB array")
    return (int(value[0]), int(value[1]), int(value[2]))


def number(style: dict[str, Any], section: str, key: str) -> float:
    value = style.get(section, {}).get(key, DEFAULT_SPARK_STYLE[section][key])
    if not isinstance(value, int | float):
        raise ValueError(f"style number {section}.{key} must be numeric")
    return float(value)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {key: value.copy() if isinstance(value, dict) else value for key, value in base.items()}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged
