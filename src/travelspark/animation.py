from __future__ import annotations

import hashlib
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
        "output_format": "gif",
        "width": width,
        "height": height,
        "storyboard": mode,
        "frames": frames,
        "fps": fps,
        "point_count": len(points),
        "cluster_count": len(clusters),
        "bounds": bounds.as_dict(),
    }


def render_still(
    points: list[PhotoPoint],
    output: Path,
    *,
    bounds: Bounds,
    style: dict,
    base_map: Image.Image,
    width: int = 1280,
    height: int = 720,
    effect: str = "none",
    cluster_radius_km: float = 8.0,
    progress: Callable[[str], None] | None = None,
) -> dict:
    if not points:
        raise ValueError("no photos with GPS remain after filtering")
    output.parent.mkdir(parents=True, exist_ok=True)
    if progress is not None:
        progress("preparing still frame")
    base = base_map.resize((width, height)).convert("RGBA")
    clusters = cluster_points(points, cluster_radius_km)
    if effect == "none":
        frame = base.convert("RGB")
    elif effect == "glow":
        frame = _compose_frame(
            base,
            points,
            clusters,
            bounds=bounds,
            style=style,
            frame_index=0,
            frame_count=1,
            mode="all-points",
        )
    else:
        raise ValueError(f"unknown effect {effect!r}; use none or glow")
    output_format = _output_format(output)
    if output_format == "jpeg":
        frame.save(output, format="JPEG", quality=92, optimize=True)
    elif output_format == "png":
        frame.save(output, format="PNG")
    elif output_format == "gif":
        frame.convert("P", palette=Image.ADAPTIVE, colors=256).save(output, format="GIF")
    else:
        raise ValueError(f"unsupported output extension: {output.suffix or '<none>'}")
    if progress is not None:
        progress(f"done: {output}")
    return {
        "output": str(output),
        "output_format": output_format,
        "width": width,
        "height": height,
        "storyboard": "all-points",
        "frames": 1,
        "effect": effect,
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
    if mode == "ambient-spark":
        _paint_ambient_spark_frame(
            glow_layer,
            marker_layer,
            points,
            clusters,
            bounds=bounds,
            style=style,
            frame_index=frame_index,
            frame_count=frame_count,
        )
        frame.alpha_composite(glow_layer)
        frame.alpha_composite(marker_layer)
        return frame.convert("RGB")
    if mode == "all-points":
        activations = _all_point_activations(points)
    elif mode == "timeline":
        activations = _timeline_activations(points, frame_index, frame_count)
    elif mode == "cluster":
        activations = _cluster_activations(clusters, frame_index, frame_count)
    elif mode == "constellation":
        activations = _constellation_activations(points, frame_index, frame_count)
    else:
        raise ValueError(f"unknown mode {mode!r}; use all-points, ambient-spark, timeline, cluster, or constellation")
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


def _all_point_activations(points: list[PhotoPoint]) -> list[tuple[float, float, int, float]]:
    return [(point.latitude, point.longitude, 1, 1.0) for point in points]


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


def _paint_ambient_spark_frame(
    glow_layer: Image.Image,
    marker_layer: Image.Image,
    points: list[PhotoPoint],
    clusters: list[Cluster],
    *,
    bounds: Bounds,
    style: dict,
    frame_index: int,
    frame_count: int,
) -> None:
    glow = color(style, "activation", "glow_color")
    marker = color(style, "activation", "marker_color")
    outline = color(style, "activation", "marker_outline_color")
    glow_draw = ImageDraw.Draw(glow_layer, "RGBA")
    phase = frame_index / max(1, frame_count)
    radius_scale = _ambient_radius_scale(bounds)
    cluster_blur = max(3, int(round(7 * radius_scale)))
    spark_blur = max(2, int(round(5 * radius_scale)))
    for index, cluster in enumerate(clusters):
        x, y = project_to_pixel(cluster.longitude, cluster.latitude, bounds=bounds, width=glow_layer.width, height=glow_layer.height)
        if x < -120 or y < -120 or x > glow_layer.width + 120 or y > glow_layer.height + 120:
            continue
        seed = _stable_units(f"cluster:{index}:{cluster.latitude:.6f}:{cluster.longitude:.6f}", 3)
        pulse = 0.96 + 0.04 * math.sin(2.0 * math.pi * phase + seed[0] * math.tau)
        radius = min(56.0, max(24.0, 18.0 + math.sqrt(cluster.count) * 5.0 + seed[1] * 8.0)) * radius_scale * pulse
        alpha = int((8 + seed[2] * 6) * radius_scale)
        glow_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*glow, alpha))
    blurred_cluster = glow_layer.filter(ImageFilter.GaussianBlur(radius=cluster_blur))
    glow_layer.paste(blurred_cluster)

    # Ambient spark should not render one animated glow per photo.  In dense
    # libraries that turns a country into a giant blob.  Use one spark site per
    # geographic cluster; the cluster glow above still communicates density.
    for index, cluster in enumerate(clusters):
        seed = _stable_units(f"site:{index}:{cluster.count}:{cluster.latitude:.6f}:{cluster.longitude:.6f}", 8)
        period = 72.0 + seed[0] * 96.0
        point_phase = seed[1] * period
        wave = (math.sin(math.tau * (frame_index + point_phase) / period) + 1.0) / 2.0
        gate = _smoothstep(0.62, 0.98, wave)
        if gate <= 0.02:
            continue
        min_intensity = 0.04 + seed[3] * 0.06
        max_intensity = 0.22 + seed[4] * 0.28
        intensity = min_intensity + (max_intensity - min_intensity) * gate
        if intensity < 0.08:
            continue
        x, y = project_to_pixel(cluster.longitude, cluster.latitude, bounds=bounds, width=glow_layer.width, height=glow_layer.height)
        jitter = 0.45 * radius_scale
        x += math.sin(math.tau * phase + seed[5] * math.tau) * jitter
        y += math.cos(math.tau * phase + seed[6] * math.tau) * jitter
        if x < -80 or y < -80 or x > glow_layer.width + 80 or y > glow_layer.height + 80:
            continue
        glow_radius = (8.0 + seed[7] * 22.0) * radius_scale
        core_radius = max(0.65, (0.8 + seed[2] * 1.4) * math.sqrt(radius_scale))
        glow_alpha = int(70 * intensity * radius_scale)
        marker_alpha = int(155 * intensity)
        glow_draw.ellipse((x - glow_radius, y - glow_radius, x + glow_radius, y + glow_radius), fill=(*glow, glow_alpha))
        _draw_soft_pinpoint(marker_layer, x, y, core_radius, marker, outline, marker_alpha)
    blurred_sparks = glow_layer.filter(ImageFilter.GaussianBlur(radius=spark_blur))
    glow_layer.paste(blurred_sparks)


def _ambient_radius_scale(bounds: Bounds) -> float:
    """Return a screen-space glow scale for ambient spark.

    Spark radii that look good on a city or country crop become continent-sized
    on a world map.  Scale radii by longitude span so global scenes keep sparks
    compact while regional scenes retain the soft glow.
    """
    lon_span = max(0.1, bounds.max_lon - bounds.min_lon)
    if lon_span >= 240:
        return 0.38
    if lon_span >= 120:
        return 0.48
    if lon_span >= 70:
        return 0.62
    if lon_span >= 35:
        return 0.78
    return 1.0


def _draw_soft_pinpoint(
    marker_layer: Image.Image,
    x: float,
    y: float,
    radius: float,
    marker: tuple[int, int, int],
    outline: tuple[int, int, int],
    alpha: int,
) -> None:
    scale = 3
    pad = max(5, int(math.ceil((radius + 2.0) * scale)))
    surface = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(surface, "RGBA")
    center = pad
    scaled_radius = radius * scale
    draw.ellipse(
        (
            center - scaled_radius - 0.8,
            center - scaled_radius - 0.8,
            center + scaled_radius + 0.8,
            center + scaled_radius + 0.8,
        ),
        fill=(*outline, int(alpha * 0.22)),
    )
    draw.ellipse(
        (
            center - scaled_radius,
            center - scaled_radius,
            center + scaled_radius,
            center + scaled_radius,
        ),
        fill=(*marker, min(210, alpha + 18)),
    )
    surface = surface.resize((max(1, pad * 2 // scale), max(1, pad * 2 // scale)), Image.Resampling.LANCZOS)
    marker_layer.alpha_composite(surface, (int(round(x)) - surface.width // 2, int(round(y)) - surface.height // 2))


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


def _output_format(output: Path) -> str:
    suffix = output.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "jpeg"
    if suffix == ".png":
        return "png"
    if suffix == ".gif":
        return "gif"
    return ""


def _stable_units(value: str, count: int) -> list[float]:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    units = []
    for index in range(count):
        start = (index * 4) % (len(digest) - 4)
        raw = int.from_bytes(digest[start : start + 4], "big")
        units.append(raw / 0xFFFFFFFF)
    return units


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 == edge1:
        return 1.0 if value >= edge1 else 0.0
    x = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return x * x * (3.0 - 2.0 * x)
