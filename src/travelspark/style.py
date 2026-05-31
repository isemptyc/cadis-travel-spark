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

STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "spark-night": DEFAULT_SPARK_STYLE,
    "puzzle-pale": {
        "activation": {
            "glow_color": [255, 255, 255],
            "marker_color": [255, 255, 255],
            "marker_outline_color": [90, 59, 16],
            "min_glow_radius_px": 16,
            "max_glow_radius_px": 58,
        },
    },
}


def load_style(path: Path | None, *, style_id: str = "spark-night") -> dict[str, Any]:
    base = STYLE_PRESETS.get(_normalize_style_id(style_id), DEFAULT_SPARK_STYLE)
    if path is None:
        return _deep_merge(DEFAULT_SPARK_STYLE, base)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"style must be a JSON object: {path}")
    return _deep_merge(_deep_merge(DEFAULT_SPARK_STYLE, base), payload)


def load_cadis_style_profile(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"style must be a JSON object: {path}")
    if payload.get("profile") != "cadis.semantic_world.map_style":
        return None
    return payload


def color(style: dict[str, Any], section: str, key: str) -> tuple[int, int, int]:
    value = style.get(section, {}).get(key, DEFAULT_SPARK_STYLE[section][key])
    if isinstance(value, str):
        return _hex_color(value)
    if not isinstance(value, list | tuple) or len(value) < 3:
        raise ValueError(f"style color {section}.{key} must be an RGB array or #RRGGBB string")
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
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_style_id(style_id: str) -> str:
    return style_id.strip().lower().replace("_", "-")


def _hex_color(value: str) -> tuple[int, int, int]:
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        raise ValueError(f"style color must be #RRGGBB, got {value!r}")
    return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
