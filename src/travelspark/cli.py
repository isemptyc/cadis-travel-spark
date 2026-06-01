from __future__ import annotations

import argparse
import json
from pathlib import Path

from .animation import render_gif, render_still
from .cluster import cluster_points
from .engine import DEFAULT_MAP_DATASET_CATALOG_ROOT, CadisMapRenderEngine, scene_bounds, scene_country_iso
from .exif import export_points_json, extract_photo_points
from .progress import Progress
from .scope import cadis_country_lookup, filter_points_for_scene
from .storyboard import load_storyboard_preset, storyboard_mode
from .style import load_cadis_style_profile, load_style
from .timeline_scene import write_timeline_scene_package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render EXIF GPS travel traces as a semantic travel presentation.")
    parser.add_argument("photos_path", type=Path, help="Folder containing photos.")
    parser.add_argument("--scene-id", required=True, help="CADIS map scene id, e.g. tw, world_8192, lon_env_europe.")
    parser.add_argument("--map-style", default="spark-night", help="Map style id, e.g. spark-night or puzzle-pale.")
    parser.add_argument("--output", type=Path, default=None, help="Optional image/GIF output path. Omit for the default online preview when using a visual preset.")
    parser.add_argument("--storyboard", choices=["all-points", "ambient-spark", "timeline", "cluster", "constellation"], default="all-points")
    parser.add_argument("--storyboard-preset", choices=["spark-drift"], default=None, help="Built-in visual storyboard preset.")
    parser.add_argument("--mode", choices=["timeline", "cluster", "constellation"], default=None, help="Deprecated alias for --storyboard.")
    parser.add_argument("--effect", choices=["none", "glow"], default="none", help="Presentation effect layer. Use none for CADIS-rendered style fidelity.")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--frames", type=int, default=96)
    parser.add_argument("--fps", type=int, default=18)
    parser.add_argument("--cluster-radius-km", type=float, default=8.0)
    parser.add_argument("--style", type=Path, default=None, help="Optional local spark overlay style JSON.")
    parser.add_argument("--catalog-root", default=DEFAULT_MAP_DATASET_CATALOG_ROOT, help="CADIS map dataset catalog root.")
    parser.add_argument("--dataset-root", type=Path, default=None, help="Optional local CADIS map dataset root.")
    parser.add_argument("--cache-root", type=Path, default=None, help="Optional CADIS map renderer cache root.")
    parser.add_argument("--output-root", type=Path, default=Path(".travelspark-output"), help="Renderer output root.")
    parser.add_argument("--scope-policy", choices=["filter", "strict", "none"], default="filter")
    parser.add_argument("--country-filter", choices=["auto", "yes", "no"], default="auto", help="Use cadis lookup for country-scope filtering.")
    parser.add_argument(
        "--use-exiftool",
        choices=["auto", "yes", "no"],
        default="auto",
        help="EXIF reader policy: auto prefers exiftool and falls back to Pillow, yes requires exiftool, no uses Pillow only.",
    )
    parser.add_argument("--points-json", type=Path, default=None, help="Optional JSON export of rendered GPS points.")
    parser.add_argument("--report-json", type=Path, default=None, help="Optional render report JSON path.")
    parser.add_argument("--export-scene", type=Path, default=None, help="Optional browser-playable timeline scene JSON export.")
    parser.add_argument("--player-html", type=Path, default=None, help="Optional HTML player path for --export-scene. Defaults beside the scene JSON.")
    parser.add_argument("--preflight-only", action="store_true", help="Extract/filter points and write report without rendering GIF.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.width < 320 or args.height < 240:
        raise SystemExit("--width/--height are too small")
    if args.frames < 2:
        raise SystemExit("--frames must be at least 2")
    try:
        storyboard_preset = load_storyboard_preset(args.storyboard_preset)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    storyboard = storyboard_mode(storyboard_preset, args.mode or args.storyboard)
    effect = "glow" if storyboard_preset is not None and args.effect == "none" else args.effect
    output, export_scene = _presentation_targets(output=args.output, export_scene=args.export_scene, storyboard=storyboard, storyboard_preset=args.storyboard_preset)
    output_format = _output_format(output) if output is not None else ""
    if output is not None and output_format not in {"jpeg", "png", "gif"}:
        raise SystemExit("--output must end with .jpg, .jpeg, .png, or .gif")
    if storyboard != "all-points" and effect == "none":
        raise SystemExit("--effect glow is required for animated storyboard modes until layered hand-off is available")
    if storyboard != "all-points" and output is not None and output_format != "gif":
        raise SystemExit("animated storyboard modes require .gif output")
    if export_scene is not None and storyboard != "ambient-spark":
        raise SystemExit("--export-scene currently supports --storyboard-preset spark-drift / ambient-spark only")

    progress = Progress(enabled=not args.quiet)
    points = extract_photo_points(
        args.photos_path,
        use_exiftool=args.use_exiftool,
        progress=progress.step,
        status=progress.say,
    )
    if not points:
        raise SystemExit(f"No photos with GPS EXIF found in {args.photos_path}")

    engine = CadisMapRenderEngine(
        scene_id=args.scene_id,
        output_root=args.output_root,
        cache_root=args.cache_root,
        catalog_root=args.catalog_root,
        dataset_root=args.dataset_root,
    )
    progress.say("loading scene metadata")
    scene = engine.scene_metadata()
    bounds = scene_bounds(scene)
    country_lookup = None
    country_iso = scene_country_iso(args.scene_id)
    in_bounds_count = sum(1 for point in points if bounds.contains(point.latitude, point.longitude))
    if args.country_filter == "yes" or _auto_country_lookup_enabled(args.country_filter, country_iso=country_iso, in_bounds_count=in_bounds_count):
        country_lookup = cadis_country_lookup()
        if country_lookup is None and args.country_filter == "yes":
            raise SystemExit("cadis lookup is unavailable; install the pinned cadis wheel or use --country-filter no")
    elif args.country_filter == "auto" and country_iso is not None and in_bounds_count > 5000:
        progress.say(
            f"skipping CADIS country lookup in auto mode for {in_bounds_count} in-bounds point(s); "
            "use --country-filter yes for strict country polygon filtering"
        )

    progress.say("filtering points for scene scope")
    scope = filter_points_for_scene(
        points,
        bounds=bounds,
        scene_country_iso=country_iso,
        policy=args.scope_policy,
        country_lookup=country_lookup,
        progress=progress.step,
    )
    progress.say(f"scene scope kept {len(scope.kept)} point(s), filtered {len(scope.skipped)}")
    if args.points_json:
        progress.say(f"writing points JSON: {args.points_json}")
        export_points_json(scope.kept, args.points_json)

    report = _preflight_report(
        args=args,
        scene=scene,
        total_count=len(points),
        scope=scope,
        storyboard=storyboard,
        effect=effect,
    )
    if args.preflight_only:
        _write_report(args.report_json, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    style = load_style(args.style, style_id=args.map_style)
    cadis_style_profile = load_cadis_style_profile(args.style)
    if effect == "none":
        base_map = engine.render_marked_map(
            points=scope.kept,
            map_style=args.map_style,
            width=args.width,
            height=args.height,
            crop_bounds=None,
            style_profile=cadis_style_profile,
        )
        render_width, render_height = _aspect_preserving_size(base_map.image.width, base_map.image.height, args.width, args.height)
        render_report = render_still(
            scope.kept,
            output,
            bounds=base_map.bounds,
            style=style,
            base_map=base_map.image,
            width=render_width,
            height=render_height,
            effect="none",
            cluster_radius_km=args.cluster_radius_km,
            progress=progress.say,
        )
    elif storyboard == "all-points":
        base_map = engine.render_base_map(
            map_style=args.map_style,
            width=args.width,
            height=args.height,
            crop_bounds=None,
            style_profile=cadis_style_profile,
        )
        render_width, render_height = _aspect_preserving_size(base_map.image.width, base_map.image.height, args.width, args.height)
        render_report = render_still(
            scope.kept,
            output,
            bounds=base_map.bounds,
            style=style,
            base_map=base_map.image,
            width=render_width,
            height=render_height,
            effect="glow",
            cluster_radius_km=args.cluster_radius_km,
            progress=progress.say,
        )
    else:
        base_map = engine.render_base_map(
            map_style=args.map_style,
            width=args.width,
            height=args.height,
            crop_bounds=None,
            style_profile=cadis_style_profile,
        )
        render_width, render_height = _aspect_preserving_size(base_map.image.width, base_map.image.height, args.width, args.height)
        if output is not None:
            render_report = render_gif(
                scope.kept,
                output,
                bounds=base_map.bounds,
                style=style,
                base_map=base_map.image,
                width=render_width,
                height=render_height,
                mode=storyboard,
                frames=args.frames,
                fps=args.fps,
                cluster_radius_km=args.cluster_radius_km,
                progress=progress.say,
                frame_progress=progress.step,
            )
        else:
            render_report = {
                "output": None,
                "output_format": "timeline-scene",
                "width": render_width,
                "height": render_height,
                "storyboard": storyboard,
                "frames": args.frames,
                "fps": args.fps,
                "point_count": len(scope.kept),
                "cluster_count": len(cluster_points(scope.kept, args.cluster_radius_km)),
                "bounds": base_map.bounds.as_dict(),
            }
        render_report["effect"] = "glow"
    if output is not None and output != args.output:
        render_report["output"] = str(output)
    report |= render_report
    report["base_map"] = base_map.metadata
    if export_scene is not None:
        player_html = args.player_html or export_scene.with_suffix(".html")
        progress.say(f"writing timeline scene: {export_scene}")
        report["timeline_scene"] = write_timeline_scene_package(
            scene_json=export_scene,
            points=scope.kept,
            base_map=base_map,
            style=style,
            storyboard=storyboard,
            storyboard_preset=args.storyboard_preset,
            width=render_report["width"],
            height=render_report["height"],
            frames=args.frames,
            fps=args.fps,
            cluster_radius_km=args.cluster_radius_km,
            player_html=player_html,
        )
    _write_report(args.report_json, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _preflight_report(
    *,
    args: argparse.Namespace,
    scene: dict,
    total_count: int,
    scope,
    storyboard: str,
    effect: str,
) -> dict:
    return {
        "photos_path": str(args.photos_path),
        "scene_id": args.scene_id,
        "map_style": args.map_style,
        "storyboard": storyboard,
        "storyboard_preset": args.storyboard_preset,
        "effect": effect,
        "scene": scene,
        "scope_policy": args.scope_policy,
        "point_count_total": total_count,
        "point_count_rendered": len(scope.kept),
        "point_count_filtered": len(scope.skipped),
        "filtered_reasons": scope.skipped_reasons,
        "detected_countries": scope.detected_countries,
    }


def _output_format(output: Path) -> str:
    suffix = output.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "jpeg"
    if suffix == ".png":
        return "png"
    if suffix == ".gif":
        return "gif"
    return ""



def _auto_country_lookup_enabled(policy: str, *, country_iso: str | None, in_bounds_count: int) -> bool:
    return policy == "auto" and country_iso is not None and in_bounds_count <= 5000

def _presentation_targets(*, output: Path | None, export_scene: Path | None, storyboard: str, storyboard_preset: str | None) -> tuple[Path | None, Path | None]:
    if storyboard_preset is not None and output is None and export_scene is None:
        return None, Path("timeline-scene.json")
    if storyboard == "all-points" and output is None:
        return Path("travel.jpg"), export_scene
    return output, export_scene


def _write_report(path: Path | None, report: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _aspect_preserving_size(source_width: int, source_height: int, max_width: int, max_height: int) -> tuple[int, int]:
    scale = min(max_width / source_width, max_height / source_height)
    width = max(1, int(round(source_width * scale)))
    height = max(1, int(round(source_height * scale)))
    return width, height
