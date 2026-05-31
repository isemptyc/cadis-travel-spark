# Onboarding Smoke Test

This checklist is the first acceptance gate for TravelSpark PoC onboarding.
Run it from a clean clone, not from a development checkout with `PYTHONPATH`.

## Clean Clone

```bash
git clone https://github.com/isemptyc/cadis-travel-spark.git
cd cadis-travel-spark
./install.sh
source .venv/bin/activate
```

Confirm imports and pinned versions:

```bash
python -c "import cadis_map_render, travelspark; print(cadis_map_render.__version__); print('travelspark import ok')"
```

Expected:

```text
0.3.32
travelspark import ok
```

## Still Output

Run the style-fidelity path:

```bash
travelspark /path/to/photos \
  --scene-id world_8192 \
  --map-style spark-night \
  --output travel.jpg \
  --report-json travel_report.json
```

Expected report fields:

```json
{
  "storyboard": "all-points",
  "effect": "none",
  "output_format": "jpeg",
  "frames": 1,
  "base_map": {
    "source": "cadis-map-render",
    "render_type": "map",
    "style_id": "spark-night",
    "cadis_style_id": "memory_atlas_night_v1"
  }
}
```

Check that `travel.jpg` exists and visually uses the night atlas style.

## Animated Output

Run the current presentation effect path:

```bash
travelspark /path/to/photos \
  --scene-id world_8192 \
  --map-style spark-night \
  --storyboard timeline \
  --effect glow \
  --output travel.gif \
  --report-json travel_gif_report.json
```

Expected report fields:

```json
{
  "storyboard": "timeline",
  "effect": "glow",
  "output_format": "gif",
  "base_map": {
    "source": "cadis-map-render",
    "render_type": "base_map",
    "style_id": "spark-night",
    "cadis_style_id": "memory_atlas_night_v1"
  }
}
```

Check that `travel.gif` exists and animates.

## CDN Mode

Do at least one run without `--dataset-root`. This verifies the public map
dataset CDN path and platform cache.

```bash
travelspark /path/to/photos \
  --scene-id world_8192 \
  --map-style spark-night \
  --output travel_cdn.jpg \
  --report-json travel_cdn_report.json
```

Expected:

- The map dataset downloads/caches if not already present.
- `travel_cdn.jpg` is created.
- `base_map.cadis_style_id` is `memory_atlas_night_v1`.

## Negative Checks

These should fail with clear messages:

```bash
travelspark /path/to/photos --scene-id world_8192 --storyboard timeline --effect none --output bad.gif
travelspark /path/to/photos --scene-id world_8192 --storyboard timeline --effect glow --output bad.jpg
travelspark /path/to/photos --scene-id world_8192 --output bad.bmp
```

Expected:

- Animated storyboards require `--effect glow`.
- Animated storyboards require `.gif`.
- Unsupported output extensions are rejected.

## Current PoC Limits

- Layer hand-off is not implemented.
- `effect=glow` is an experimental app-layer presentation effect.
- `effect=none` is the canonical style-fidelity path.
- Video export is not implemented.
