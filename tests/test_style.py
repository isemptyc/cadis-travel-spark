import json

from travelspark.style import color, load_cadis_style_profile, load_style, number


def test_map_style_selects_overlay_preset():
    style = load_style(None, style_id="puzzle-pale")

    assert color(style, "activation", "glow_color") == (255, 255, 255)
    assert number(style, "activation", "max_glow_radius_px") == 58


def test_spark_night_matches_memory_atlas_night_overlay_values():
    style = load_style(None, style_id="spark-night")

    assert color(style, "activation", "glow_color") == (255, 211, 111)
    assert color(style, "activation", "marker_color") == (255, 240, 170)
    assert color(style, "activation", "marker_outline_color") == (27, 36, 64)
    assert number(style, "activation", "min_glow_radius_px") == 30.0
    assert number(style, "activation", "max_glow_radius_px") == 142.0


def test_external_style_accepts_cadis_hex_colors(tmp_path):
    path = tmp_path / "memory_atlas_night_v1.json"
    path.write_text(
        json.dumps(
            {
                "activation": {
                    "glow_color": "#f7d36b",
                    "marker_color": "#fff4c2",
                }
            }
        ),
        encoding="utf-8",
    )

    style = load_style(path, style_id="spark-night")

    assert color(style, "activation", "glow_color") == (247, 211, 107)
    assert color(style, "activation", "marker_color") == (255, 244, 194)


def test_external_cadis_style_profile_is_available_for_basemap(tmp_path):
    path = tmp_path / "memory_atlas_night_v1.json"
    path.write_text(
        json.dumps(
            {
                "profile": "cadis.semantic_world.map_style",
                "style_id": "memory_atlas_night_v1",
                "base": {
                    "sea": "#07121f",
                    "land": "#2e4a40",
                },
            }
        ),
        encoding="utf-8",
    )

    profile = load_cadis_style_profile(path)

    assert profile is not None
    assert profile["style_id"] == "memory_atlas_night_v1"
