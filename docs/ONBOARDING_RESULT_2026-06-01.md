# Onboarding Result: 2026-06-01

## Summary

Clean-clone onboarding passed for the TravelSpark PoC.

The test verified:

- fresh GitHub clone
- `./install.sh`
- vendored wheel install
- import/version check
- still JPEG output with `effect=none`
- animated GIF output with `effect=glow`
- CDN mode without `--dataset-root`
- documented negative checks

## Environment

```text
Date: 2026-06-01
Machine: local macOS development machine
Clone path: /private/tmp/cadis-travel-spark-onboarding-20260601-01
Photo input: /Volumes/My Book/2025.09.25 Backup/Desktop/2024.09 西歐
Local map dataset: /Volumes/My Book/Cadis-SaaS-Datasets/cadis-map-dataset/scenes
```

The clean clone installer created a Python 3.14 virtual environment from the
system `python3`.

Installed/imported package check:

```text
cadis-map-render 0.3.32
travelspark import ok
```

## Install

Commands:

```bash
git clone https://github.com/isemptyc/cadis-travel-spark.git /private/tmp/cadis-travel-spark-onboarding-20260601-01
cd /private/tmp/cadis-travel-spark-onboarding-20260601-01
./install.sh
.venv/bin/python -c "import cadis_map_render, travelspark; print(cadis_map_render.__version__); print('travelspark import ok')"
```

Result: passed.

## Still JPEG

Command:

```bash
.venv/bin/travelspark '/Volumes/My Book/2025.09.25 Backup/Desktop/2024.09 西歐' \
  --scene-id world_8192 \
  --dataset-root '/Volumes/My Book/Cadis-SaaS-Datasets/cadis-map-dataset/scenes' \
  --map-style spark-night \
  --output travel.jpg \
  --report-json travel_report.json \
  --quiet
```

Result: passed.

Key report fields:

```json
{
  "storyboard": "all-points",
  "effect": "none",
  "output_format": "jpeg",
  "frames": 1,
  "point_count_rendered": 196,
  "base_map": {
    "source": "cadis-map-render",
    "render_type": "map",
    "scene_id": "world_8192",
    "scene_version": "v0.1.10",
    "style_id": "spark-night",
    "cadis_style_id": "memory_atlas_night_v1",
    "activation_mode": "point_cluster"
  }
}
```

Output:

```text
travel.jpg 1280x720 JPEG
```

## Animated GIF

Command:

```bash
.venv/bin/travelspark '/Volumes/My Book/2025.09.25 Backup/Desktop/2024.09 西歐' \
  --scene-id world_8192 \
  --dataset-root '/Volumes/My Book/Cadis-SaaS-Datasets/cadis-map-dataset/scenes' \
  --map-style spark-night \
  --storyboard timeline \
  --effect glow \
  --output travel.gif \
  --report-json travel_gif_report.json \
  --frames 4 \
  --quiet
```

Result: passed.

Key report fields:

```json
{
  "storyboard": "timeline",
  "effect": "glow",
  "output_format": "gif",
  "frames": 4,
  "point_count_rendered": 196,
  "base_map": {
    "source": "cadis-map-render",
    "render_type": "base_map",
    "scene_id": "world_8192",
    "scene_version": "v0.1.10",
    "style_id": "spark-night",
    "cadis_style_id": "memory_atlas_night_v1"
  }
}
```

Output:

```text
travel.gif 1280x720 GIF
```

## CDN Mode

Command:

```bash
.venv/bin/travelspark '/Volumes/My Book/2025.09.25 Backup/Desktop/2024.09 西歐' \
  --scene-id world_8192 \
  --map-style spark-night \
  --output travel_cdn.jpg \
  --report-json travel_cdn_report.json \
  --quiet
```

Result: passed.

Key report fields:

```json
{
  "storyboard": "all-points",
  "effect": "none",
  "output_format": "jpeg",
  "frames": 1,
  "point_count_rendered": 196,
  "base_map": {
    "source": "cadis-map-render",
    "render_type": "map",
    "scene_id": "world_8192",
    "scene_version": "v0.1.11",
    "style_id": "spark-night",
    "cadis_style_id": "memory_atlas_night_v1",
    "activation_mode": "point_cluster"
  }
}
```

Output:

```text
travel_cdn.jpg 1280x720 JPEG
```

## Dataset Version Note

The local dataset root and public CDN did not resolve to the same scene
version:

```text
local dataset root: world_8192 v0.1.10
CDN mode:          world_8192 v0.1.11
```

This is not a TravelSpark failure. It means visual or metadata differences may
appear when comparing a local dataset-root run against CDN mode. CDN mode is
the public onboarding path.

## Negative Checks

These checks failed early with clear messages:

```bash
.venv/bin/travelspark ... --storyboard timeline --effect none --output bad.gif
```

```text
--effect glow is required for animated storyboard modes until layered hand-off is available
```

```bash
.venv/bin/travelspark ... --storyboard timeline --effect glow --output bad.jpg
```

```text
animated storyboard modes require .gif output
```

```bash
.venv/bin/travelspark ... --output bad.bmp
```

```text
--output must end with .jpg, .jpeg, .png, or .gif
```

## Remaining Risks

- Windows PowerShell onboarding has not been run.
- CDN cold-cache timing was not measured separately.
- Visual QA was limited to file creation and image metadata, not detailed pixel inspection.
- `effect=glow` remains an experimental app-layer effect until layer hand-off exists.
- Python 3.14 worked in this clean install, but the advertised support remains controlled by `pyproject.toml`.
