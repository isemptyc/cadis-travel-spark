from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
from typing import Any

from PIL import Image

from .animation import _stable_units
from .cluster import cluster_points
from .engine import BaseMap
from .exif import PhotoPoint
from .geo import project_to_pixel
from .style import color


def build_timeline_scene(
    *,
    points: list[PhotoPoint],
    base_map: BaseMap,
    style: dict[str, Any],
    storyboard: str,
    storyboard_preset: str | None,
    width: int,
    height: int,
    frames: int,
    fps: int,
    cluster_radius_km: float,
    base_map_src: str,
) -> dict[str, Any]:
    clusters = cluster_points(points, cluster_radius_km)
    duration_ms = int(round(frames / max(1, fps) * 1000))
    return {
        "profile": "cadis.travel_spark.timeline_scene",
        "schema_version": 1,
        "scene_id": base_map.scene_id,
        "scene_version": base_map.scene_version,
        "storyboard": {
            "mode": storyboard,
            "preset": storyboard_preset,
        },
        "viewport": {
            "width": width,
            "height": height,
        },
        "timing": {
            "duration_ms": duration_ms,
            "fps_hint": fps,
            "frames_hint": frames,
            "loop": True,
        },
        "bounds": base_map.bounds.as_dict(),
        "base_map": {
            "type": "image",
            "src": base_map_src,
            "width": width,
            "height": height,
            "metadata": base_map.metadata,
        },
        "style": {
            "glow_color": color(style, "activation", "glow_color"),
            "marker_color": color(style, "activation", "marker_color"),
            "marker_outline_color": color(style, "activation", "marker_outline_color"),
        },
        "effects": _ambient_spark_effects(points, clusters, base_map=base_map, width=width, height=height),
    }


def write_timeline_scene_package(
    *,
    scene_json: Path,
    points: list[PhotoPoint],
    base_map: BaseMap,
    style: dict[str, Any],
    storyboard: str,
    storyboard_preset: str | None,
    width: int,
    height: int,
    frames: int,
    fps: int,
    cluster_radius_km: float,
    player_html: Path | None = None,
) -> dict[str, Any]:
    scene_json.parent.mkdir(parents=True, exist_ok=True)
    asset_dir = scene_json.parent / f"{scene_json.stem}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    base_map_path = asset_dir / "basemap.png"
    base_map.image.resize((width, height), Image.Resampling.LANCZOS).save(base_map_path, format="PNG")
    scene = build_timeline_scene(
        points=points,
        base_map=base_map,
        style=style,
        storyboard=storyboard,
        storyboard_preset=storyboard_preset,
        width=width,
        height=height,
        frames=frames,
        fps=fps,
        cluster_radius_km=cluster_radius_km,
        base_map_src=base_map_path.relative_to(scene_json.parent).as_posix(),
    )
    scene_json.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if player_html is not None:
        scene_for_player = copy.deepcopy(scene)
        scene_for_player["base_map"]["src"] = Path(os.path.relpath(base_map_path, player_html.parent)).as_posix()
        write_player_html(player_html, scene=scene_for_player)
    return {
        "timeline_scene_json": str(scene_json),
        "timeline_player_html": str(player_html) if player_html is not None else None,
        "timeline_base_map": str(base_map_path),
    }


def write_player_html(player_html: Path, *, scene: dict[str, Any]) -> None:
    player_html.parent.mkdir(parents=True, exist_ok=True)
    scene_payload = json.dumps(scene, ensure_ascii=False)
    player_html.write_text(_PLAYER_HTML.replace("__TRAVELSPARK_SCENE__", scene_payload), encoding="utf-8")


def _ambient_spark_effects(points, clusters, *, base_map: BaseMap, width: int, height: int) -> dict[str, Any]:
    cluster_rows = []
    for index, cluster in enumerate(clusters):
        x, y = project_to_pixel(cluster.longitude, cluster.latitude, bounds=base_map.bounds, width=width, height=height)
        seed = _stable_units(f"cluster:{index}:{cluster.latitude:.6f}:{cluster.longitude:.6f}", 3)
        cluster_rows.append(
            {
                "x": x,
                "y": y,
                "count": cluster.count,
                "phase": seed[0] * math.tau,
                "radius": min(56.0, max(24.0, 18.0 + math.sqrt(cluster.count) * 5.0 + seed[1] * 8.0)),
                "alpha": int(8 + seed[2] * 6),
            }
        )
    point_rows = []
    for index, point in enumerate(points):
        x, y = project_to_pixel(point.longitude, point.latitude, bounds=base_map.bounds, width=width, height=height)
        seed = _stable_units(f"point:{index}:{point.path}:{point.latitude:.6f}:{point.longitude:.6f}", 8)
        point_rows.append(
            {
                "x": x,
                "y": y,
                "source": str(point.path),
                "period_ms": int(round((72.0 + seed[0] * 96.0) * 1000 / 18)),
                "phase_ms": int(round(seed[1] * (72.0 + seed[0] * 96.0) * 1000 / 18)),
                "min_intensity": 0.04 + seed[3] * 0.06,
                "max_intensity": 0.22 + seed[4] * 0.28,
                "core_radius": 0.8 + seed[2] * 1.4,
                "glow_radius": 8.0 + seed[7] * 22.0,
                "jitter_phase_x": seed[5] * math.tau,
                "jitter_phase_y": seed[6] * math.tau,
                "jitter_radius": 0.45,
            }
        )
    return {
        "type": "ambient-spark",
        "clusters": cluster_rows,
        "points": point_rows,
    }


_PLAYER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TravelSpark Player</title>
  <style>
    :root { color-scheme: dark; background: #05070b; color: #f6f1df; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; grid-template-rows: 1fr auto; background: #05070b; }
    main { min-height: 0; display: grid; place-items: center; padding: 18px; }
    canvas { width: min(100%, calc(100vh * 16 / 9)); max-height: calc(100vh - 92px); border-radius: 8px; box-shadow: 0 18px 80px rgba(0,0,0,.45); background: #07101b; }
    footer { display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: center; padding: 12px 18px 18px; }
    button { border: 1px solid rgba(246,241,223,.26); color: #f6f1df; background: rgba(255,255,255,.07); border-radius: 6px; padding: 8px 13px; font: inherit; cursor: pointer; }
    button:hover { background: rgba(255,255,255,.12); }
    input[type="range"] { width: 100%; accent-color: #e7c96a; }
    .time { color: rgba(246,241,223,.72); font-variant-numeric: tabular-nums; min-width: 96px; text-align: right; }
  </style>
</head>
<body>
  <main><canvas id="stage"></canvas></main>
  <footer>
    <button id="play">Pause</button>
    <input id="scrub" type="range" min="0" max="1000" value="0">
    <div class="time" id="time">0.0s</div>
  </footer>
  <script>
    const scene = __TRAVELSPARK_SCENE__;
    const canvas = document.getElementById("stage");
    const ctx = canvas.getContext("2d");
    const playButton = document.getElementById("play");
    const scrub = document.getElementById("scrub");
    const time = document.getElementById("time");
    const width = scene.viewport.width;
    const height = scene.viewport.height;
    const duration = scene.timing.duration_ms;
    const glow = scene.style.glow_color;
    const marker = scene.style.marker_color;
    const outline = scene.style.marker_outline_color;
    canvas.width = width;
    canvas.height = height;
    canvas.style.aspectRatio = `${width} / ${height}`;
    const base = new Image();
    let playing = true;
    let startedAt = performance.now();
    let pausedAt = 0;

    function rgba(rgb, alpha) {
      return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${Math.max(0, Math.min(1, alpha))})`;
    }
    function smoothstep(edge0, edge1, value) {
      const x = Math.max(0, Math.min(1, (value - edge0) / (edge1 - edge0)));
      return x * x * (3 - 2 * x);
    }
    function drawGlow(x, y, radius, rgb, alpha) {
      const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
      gradient.addColorStop(0, rgba(rgb, alpha));
      gradient.addColorStop(0.45, rgba(rgb, alpha * 0.28));
      gradient.addColorStop(1, rgba(rgb, 0));
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fill();
    }
    function drawFrame(elapsed) {
      ctx.clearRect(0, 0, width, height);
      if (base.complete) ctx.drawImage(base, 0, 0, width, height);
      const phase = elapsed / duration;
      ctx.save();
      ctx.globalCompositeOperation = "screen";
      for (const cluster of scene.effects.clusters) {
        const pulse = 0.96 + 0.04 * Math.sin(Math.PI * 2 * phase + cluster.phase);
        drawGlow(cluster.x, cluster.y, cluster.radius * pulse, glow, cluster.alpha / 255);
      }
      for (const point of scene.effects.points) {
        const wave = (Math.sin(Math.PI * 2 * (elapsed + point.phase_ms) / point.period_ms) + 1) / 2;
        const gate = smoothstep(0.62, 0.98, wave);
        if (gate <= 0.02) continue;
        const intensity = point.min_intensity + (point.max_intensity - point.min_intensity) * gate;
        if (intensity < 0.08) continue;
        const x = point.x + Math.sin(Math.PI * 2 * phase + point.jitter_phase_x) * point.jitter_radius;
        const y = point.y + Math.cos(Math.PI * 2 * phase + point.jitter_phase_y) * point.jitter_radius;
        drawGlow(x, y, point.glow_radius, glow, 0.27 * intensity);
        ctx.fillStyle = rgba(outline, 0.09 + intensity * 0.13);
        ctx.beginPath();
        ctx.arc(x, y, point.core_radius + 0.8, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = rgba(marker, 0.16 + intensity * 0.45);
        ctx.beginPath();
        ctx.arc(x, y, point.core_radius, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
      scrub.value = String(Math.round((elapsed / duration) * 1000));
      time.textContent = `${(elapsed / 1000).toFixed(1)}s`;
    }
    function tick(now) {
      const elapsed = playing ? (now - startedAt) % duration : pausedAt;
      drawFrame(elapsed);
      requestAnimationFrame(tick);
    }
    playButton.addEventListener("click", () => {
      playing = !playing;
      if (playing) {
        startedAt = performance.now() - pausedAt;
        playButton.textContent = "Pause";
      } else {
        pausedAt = (performance.now() - startedAt) % duration;
        playButton.textContent = "Play";
      }
    });
    scrub.addEventListener("input", () => {
      pausedAt = Number(scrub.value) / 1000 * duration;
      startedAt = performance.now() - pausedAt;
      drawFrame(pausedAt);
    });
    base.onload = () => requestAnimationFrame(tick);
    base.src = scene.base_map.src;
  </script>
</body>
</html>
"""
