from __future__ import annotations

import argparse
import json
from pathlib import Path

from .animation import render_gif
from .engine import DEFAULT_MAP_DATASET_CATALOG_ROOT, CadisMapRenderEngine, scene_bounds, scene_country_iso
from .exif import export_points_json, extract_photo_points
from .progress import Progress
from .scope import cadis_country_lookup, filter_points_for_scene
from .style import load_style


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render EXIF GPS travel traces as an animated map GIF.")
    parser.add_argument("photos_path", type=Path, help="Folder containing photos.")
    parser.add_argument("--scene-id", required=True, help="CADIS map scene id, e.g. tw, world_8192, lon_env_europe.")
    parser.add_argument("--map-style", default="spark-night", help="Map style id, e.g. spark-night or puzzle-pale.")
    parser.add_argument("--output", type=Path, default=Path("travel.gif"), help="Output GIF path.")
    parser.add_argument("--mode", choices=["timeline", "cluster", "constellation"], default="timeline")
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
    parser.add_argument("--use-exiftool", choices=["auto", "yes", "no"], default="auto")
    parser.add_argument("--points-json", type=Path, default=None, help="Optional JSON export of rendered GPS points.")
    parser.add_argument("--report-json", type=Path, default=None, help="Optional render report JSON path.")
    parser.add_argument("--preflight-only", action="store_true", help="Extract/filter points and write report without rendering GIF.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.width < 320 or args.height < 240:
        raise SystemExit("--width/--height are too small")
    if args.frames < 2:
        raise SystemExit("--frames must be at least 2")

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
    if args.country_filter == "yes" or (args.country_filter == "auto" and scene_country_iso(args.scene_id) is not None):
        country_lookup = cadis_country_lookup()
        if country_lookup is None and args.country_filter == "yes":
            raise SystemExit("cadis lookup is unavailable; install the pinned cadis wheel or use --country-filter no")

    scope = filter_points_for_scene(
        points,
        bounds=bounds,
        scene_country_iso=scene_country_iso(args.scene_id),
        policy=args.scope_policy,
        country_lookup=country_lookup,
    )
    if args.points_json:
        progress.say(f"writing points JSON: {args.points_json}")
        export_points_json(scope.kept, args.points_json)

    report = _preflight_report(args=args, scene=scene, total_count=len(points), scope=scope)
    if args.preflight_only:
        _write_report(args.report_json, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    style = load_style(args.style)
    base_map = engine.render_base_map(
        map_style=args.map_style,
        width=args.width,
        height=args.height,
        crop_bounds=None,
    )
    render_report = render_gif(
        scope.kept,
        args.output,
        bounds=base_map.bounds,
        style=style,
        base_map=base_map.image,
        width=args.width,
        height=args.height,
        mode=args.mode,
        frames=args.frames,
        fps=args.fps,
        cluster_radius_km=args.cluster_radius_km,
        progress=progress.say,
        frame_progress=progress.step,
    )
    report |= render_report
    report["base_map"] = base_map.metadata
    _write_report(args.report_json, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _preflight_report(*, args: argparse.Namespace, scene: dict, total_count: int, scope) -> dict:
    return {
        "photos_path": str(args.photos_path),
        "scene_id": args.scene_id,
        "map_style": args.map_style,
        "scene": scene,
        "scope_policy": args.scope_policy,
        "point_count_total": total_count,
        "point_count_rendered": len(scope.kept),
        "point_count_filtered": len(scope.skipped),
        "filtered_reasons": scope.skipped_reasons,
        "detected_countries": scope.detected_countries,
    }


def _write_report(path: Path | None, report: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
