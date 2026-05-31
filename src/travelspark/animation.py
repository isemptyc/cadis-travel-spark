from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter

from .cluster import Cluster, cluster_points
from .exif import PhotoPoint
from .geo import Bounds, project_to_pixel
from .style import color, number


def render_gif(
    points: list[PhotoPoint],
    output: Path,
    *,
    bounds: Bounds,
    style: dict,
    base_map: Image.Image,
    width: int = 1280,
    height: int = 720,
    mode: str = "timeline",
    frames: int = 96,
    fps: int = 18,
    cluster_radius_km: float = 8.0,
    progress: Callable[[str], None] | None = None,
    frame_progress: Callable[[str, int, int], None] | None = None,
) -> dict:
    if not points:
        raise ValueError("no photos with GPS remain after filtering")
    output.parent.mkdir(parents=True, exist_ok=True)
    if progress is not None:
        progress("preparing base map")
    base = base_map.resize((width, height)).convert("RGBA")
    clusters = cluster_points(points, cluster_radius_km)
    if progress is not None:
        progress(f"generating GIF frames: {frames}")
    frame_images = []
    for i in range(frames):
        if frame_progress is not None and (i == 0 or i + 1 == frames or (i + 1) % 10 == 0):
            frame_progress("rendering frames", i + 1, frames)
        frame_images.append(
            _compose_frame(
                base,
                points,
                clusters,
                bounds=bounds,
                style=style,
                frame_index=i,
                frame_count=frames,
                mode=mode,
            )
        )
    if progress is not None:
        progress("encoding GIF")
    palette_frames = [frame.convert("P", palette=Image.ADAPTIVE, colors=256) for frame in frame_images]
    palette_frames[0].save(
        output,
        save_all=True,
        append_images=palette_frames[1:],
        duration=max(1, int(1000 / fps)),
        loop=0,
        optimize=False,
        disposal=2,
    )
    if progress is not None:
        progress(f"done: {output}")
    return {
        "output": str(output),
        "width": width,
        "height": height,
        "mode": mode,
        "frames": frames,
        "fps": fps,
        "point_count": len(points),
        "cluster_count": len(clusters),
        "bounds": bounds.as_dict(),
    }


def _compose_frame(
    base: Image.Image,
    points: list[PhotoPoint],
    clusters: list[Cluster],
    *,
    bounds: Bounds,
    style: dict,
    frame_index: int,
    frame_count: int,
    mode: str,
) -> Image.Image:
    frame = base.copy()
    glow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    marker_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer, "RGBA")
    marker_draw = ImageDraw.Draw(marker_layer, "RGBA")
    if mode == "timeline":
        activations = _timeline_activations(points, frame_index, frame_count)
    elif mode == "cluster":
        activations = _cluster_activations(clusters, frame_index, frame_count)
    elif mode == "constellation":
        activations = _constellation_activations(points, frame_index, frame_count)
    else:
        raise ValueError(f"unknown mode {mode!r}; use timeline, cluster, or constellation")
    for lat, lon, weight, intensity in activations:
        x, y = project_to_pixel(lon, lat, bounds=bounds, width=base.width, height=base.height)
        if x < -120 or y < -120 or x > base.width + 120 or y > base.height + 120:
            continue
        _draw_glow(glow_draw, marker_draw, x, y, weight=weight, intensity=intensity, style=style)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=9))
    frame.alpha_composite(glow_layer)
    frame.alpha_composite(marker_layer)
    return frame.convert("RGB")


def _timeline_activations(points: list[PhotoPoint], frame_index: int, frame_count: int) -> list[tuple[float, float, int, float]]:
    ordered = sorted(points, key=lambda p: (p.taken_at is None, p.taken_at, str(p.path)))
    trail = max(8, frame_count // 5)
    progress = frame_index / max(1, frame_count - 1)
    head = min(len(ordered) - 1, int(progress * (len(ordered) + trail)))
    rows: list[tuple[float, float, int, float]] = []
    for idx in range(max(0, head - trail), min(len(ordered), head + 1)):
        age = head - idx
        intensity = max(0.08, 1.0 - age / max(1, trail))
        point = ordered[idx]
        rows.append((point.latitude, point.longitude, 1, intensity))
    return rows


def _cluster_activations(clusters: list[Cluster], frame_index: int, frame_count: int) -> list[tuple[float, float, int, float]]:
    if not clusters:
        return []
    phase = frame_index / max(1, frame_count)
    rows: list[tuple[float, float, int, float]] = []
    ordered = sorted(clusters, key=lambda c: (-c.count, c.latitude, c.longitude))
    for idx, cluster in enumerate(ordered):
        wave = (math.sin((phase * 2.0 * math.pi) + idx * 1.37) + 1.0) / 2.0
        if wave > 0.38:
            rows.append((cluster.latitude, cluster.longitude, cluster.count, 0.25 + wave * 0.9))
    return rows


def _constellation_activations(points: list[PhotoPoint], frame_index: int, frame_count: int) -> list[tuple[float, float, int, float]]:
    phase = frame_index / max(1, frame_count)
    rows: list[tuple[float, float, int, float]] = []
    for idx, point in enumerate(points):
        wave = (math.sin(phase * 2.0 * math.pi * 2.0 + idx * 2.399) + 1.0) / 2.0
        rows.append((point.latitude, point.longitude, 1, 0.18 + wave * 0.85))
    return rows


def _draw_glow(
    glow_draw: ImageDraw.ImageDraw,
    marker_draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    *,
    weight: int,
    intensity: float,
    style: dict,
) -> None:
    glow = color(style, "activation", "glow_color")
    marker = color(style, "activation", "marker_color")
    outline = color(style, "activation", "marker_outline_color")
    min_radius = number(style, "activation", "min_glow_radius_px")
    max_radius = number(style, "activation", "max_glow_radius_px")
    radius = min(max_radius, max(min_radius, min_radius + math.sqrt(weight) * 7.0))
    alpha = int(205 * max(0.0, min(1.0, intensity)))
    glow_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*glow, alpha))
    core_radius = max(2.0, min(10.0, 2.2 + math.sqrt(weight) * 0.8))
    marker_draw.ellipse((x - core_radius - 1.4, y - core_radius - 1.4, x + core_radius + 1.4, y + core_radius + 1.4), fill=(*outline, int(alpha * 0.72)))
    marker_draw.ellipse((x - core_radius, y - core_radius, x + core_radius, y + core_radius), fill=(*marker, min(255, alpha + 35)))
