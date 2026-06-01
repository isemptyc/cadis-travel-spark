from __future__ import annotations

import json
import mimetypes
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from PIL import ExifTags, Image


PHOTO_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
    ".png",
    ".dng",
}

GPS_TAG_ID = next(k for k, v in ExifTags.TAGS.items() if v == "GPSInfo")
GPS_TAGS = {v: k for k, v in ExifTags.GPSTAGS.items()}

EXIFTOOL_BASE_ARGS = ("-json", "-n")
EXIFTOOL_QUICK_ARGS = ("-fast2",)
EXIFTOOL_GPS_DATETIME_TAGS = (
    "-GPSLatitude",
    "-GPSLongitude",
    "-DateTimeOriginal",
    "-SubSecDateTimeOriginal",
    "-OffsetTimeOriginal",
    "-CreateDate",
    "-ModifyDate",
)
EXIFTOOL_MAX_BATCH_FILES = 500
EXIFTOOL_MAX_COMMAND_BYTES = 120_000


@dataclass(frozen=True)
class PhotoPoint:
    path: Path
    latitude: float
    longitude: float
    taken_at: datetime | None = None


def find_photo_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise ValueError(f"input folder does not exist or is not a directory: {folder}")
    return sorted(path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in PHOTO_SUFFIXES)


def extract_photo_points(
    folder: Path,
    *,
    use_exiftool: str = "auto",
    progress: Callable[[str, int, int], None] | None = None,
    status: Callable[[str], None] | None = None,
) -> list[PhotoPoint]:
    if status is not None:
        status(f"scanning photos: {folder}")
    paths = find_photo_files(folder)
    if status is not None:
        status(f"found {len(paths)} candidate photo files")

    exiftool_path = shutil.which("exiftool")
    if use_exiftool in {"auto", "yes"} and exiftool_path:
        if status is not None:
            status("reading EXIF GPS with exiftool quick mode")
        points = _extract_with_exiftool(paths, skip_paths=set(), progress=progress, mode="quick")
        seen = {point.path.resolve() for point in points}
        missing = [path for path in paths if path.resolve() not in seen]
        if missing:
            if status is not None:
                status(f"running exiftool full fallback for {len(missing)} files")
            points.extend(_extract_with_exiftool(missing, skip_paths=seen, progress=progress, mode="full"))
            seen = {point.path.resolve() for point in points}
            missing = [path for path in paths if path.resolve() not in seen]
        if missing:
            if status is not None:
                status(f"running Pillow fallback for {len(missing)} files")
            points.extend(_extract_with_pillow(missing, progress=progress))
    elif use_exiftool == "yes":
        raise RuntimeError("exiftool is required by --use-exiftool yes but was not found on PATH")
    else:
        if status is not None and use_exiftool == "auto":
            status("exiftool not found; using Pillow fallback")
        points = _extract_with_pillow(paths, progress=progress)

    if status is not None:
        status(f"GPS points extracted: {len(points)}")
    return sorted(points, key=lambda p: (p.taken_at or datetime.min.replace(tzinfo=timezone.utc), str(p.path)))


def export_points_json(points: list[PhotoPoint], output: Path) -> None:
    payload = [
        {
            "path": str(point.path),
            "latitude": point.latitude,
            "longitude": point.longitude,
            "taken_at": point.taken_at.isoformat() if point.taken_at else None,
        }
        for point in points
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_with_pillow(
    paths: Iterable[Path],
    *,
    progress: Callable[[str, int, int], None] | None = None,
) -> list[PhotoPoint]:
    path_list = list(paths)
    points: list[PhotoPoint] = []
    total = len(path_list)
    for index, path in enumerate(path_list, start=1):
        if progress is not None and (index == 1 or index == total or index % 100 == 0):
            progress("parsing EXIF GPS", index, total)
        try:
            with Image.open(path) as image:
                exif = image.getexif()
                gps = exif.get_ifd(GPS_TAG_ID) if GPS_TAG_ID in exif else None
                if not gps:
                    continue
                lat = _gps_coord(gps, GPS_TAGS["GPSLatitude"], GPS_TAGS["GPSLatitudeRef"])
                lon = _gps_coord(gps, GPS_TAGS["GPSLongitude"], GPS_TAGS["GPSLongitudeRef"])
                if lat is None or lon is None:
                    continue
                points.append(PhotoPoint(path=path, latitude=lat, longitude=lon, taken_at=_taken_at_from_exif(exif)))
        except Exception:
            continue
    return points


def _extract_with_exiftool(
    paths: Iterable[Path],
    *,
    skip_paths: set[Path],
    progress: Callable[[str, int, int], None] | None = None,
    mode: str = "quick",
) -> list[PhotoPoint]:
    rows = _run_exiftool(list(paths), progress=progress, mode=mode)
    points: list[PhotoPoint] = []
    for row in rows:
        source = row.get("SourceFile")
        if not isinstance(source, str):
            continue
        path = Path(source)
        if path.resolve() in skip_paths:
            continue
        lat = _coerce_float(row.get("GPSLatitude"))
        lon = _coerce_float(row.get("GPSLongitude"))
        if lat is None or lon is None:
            continue
        points.append(
            PhotoPoint(
                path=path,
                latitude=lat,
                longitude=lon,
                taken_at=_parse_datetime(
                    row.get("SubSecDateTimeOriginal")
                    or row.get("DateTimeOriginal")
                    or row.get("CreateDate")
                    or row.get("ModifyDate"),
                    offset=row.get("OffsetTimeOriginal"),
                ),
            )
        )
    return points


def _run_exiftool(
    paths: list[Path],
    *,
    progress: Callable[[str, int, int], None] | None = None,
    mode: str = "quick",
) -> list[dict]:
    rows: list[dict] = []
    if not paths:
        return rows
    extra_args = EXIFTOOL_QUICK_ARGS if mode == "quick" else ()
    label = "parsing EXIF GPS with exiftool quick mode" if mode == "quick" else "parsing EXIF GPS with exiftool full mode"
    for batch, completed in _exiftool_batches(paths, extra_args=extra_args):
        if progress is not None:
            progress(label, completed, len(paths))
        result = subprocess.run(
            [
                "exiftool",
                *EXIFTOOL_BASE_ARGS,
                *extra_args,
                *EXIFTOOL_GPS_DATETIME_TAGS,
                *[str(path) for path in batch],
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            payload = json.loads(result.stdout)
            if isinstance(payload, list):
                rows.extend(row for row in payload if isinstance(row, dict))
    return rows


def _exiftool_batches(paths: list[Path], *, extra_args: tuple[str, ...]) -> list[tuple[list[Path], int]]:
    fixed_args = ["exiftool", *EXIFTOOL_BASE_ARGS, *extra_args, *EXIFTOOL_GPS_DATETIME_TAGS]
    fixed_bytes = sum(len(arg.encode("utf-8")) + 1 for arg in fixed_args)
    batches: list[tuple[list[Path], int]] = []
    current: list[Path] = []
    current_bytes = fixed_bytes
    completed = 0
    for path in paths:
        path_arg = str(path)
        path_bytes = len(path_arg.encode("utf-8")) + 1
        would_exceed_count = len(current) >= EXIFTOOL_MAX_BATCH_FILES
        would_exceed_bytes = bool(current) and current_bytes + path_bytes > EXIFTOOL_MAX_COMMAND_BYTES
        if would_exceed_count or would_exceed_bytes:
            completed += len(current)
            batches.append((current, completed))
            current = []
            current_bytes = fixed_bytes
        current.append(path)
        current_bytes += path_bytes
    if current:
        completed += len(current)
        batches.append((current, completed))
    return batches


def _gps_coord(gps: dict, value_tag: int, ref_tag: int) -> float | None:
    values = gps.get(value_tag)
    ref = gps.get(ref_tag)
    if not values or not ref:
        return None
    value = _rational_to_float(values[0]) + _rational_to_float(values[1]) / 60.0 + _rational_to_float(values[2]) / 3600.0
    return -value if str(ref).upper() in {"S", "W"} else value


def _rational_to_float(value: object) -> float:
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        return float(value.numerator) / float(value.denominator)
    if isinstance(value, tuple) and len(value) == 2:
        return float(value[0]) / float(value[1])
    return float(value)


def _taken_at_from_exif(exif: Image.Exif) -> datetime | None:
    for tag_id, tag_name in ExifTags.TAGS.items():
        if tag_name in {"DateTimeOriginal", "DateTimeDigitized", "DateTime"} and tag_id in exif:
            parsed = _parse_datetime(exif.get(tag_id))
            if parsed is not None:
                return parsed
    return None


def _parse_datetime(value: object, *, offset: object = None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    normalized_offset = _normalize_offset(offset)
    candidates = []
    if normalized_offset is not None and not _has_datetime_offset(text):
        candidates.append(f"{text}{normalized_offset}")
    candidates.append(text)
    for candidate in candidates:
        for fmt in (
            "%Y:%m:%d %H:%M:%S.%f%z",
            "%Y:%m:%d %H:%M:%S%z",
            "%Y:%m:%d %H:%M:%S.%f",
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(candidate, fmt)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    return None


def _normalize_offset(value: object) -> str | None:
    if not value:
        return None
    text = str(value).strip().upper()
    if text == "Z":
        return "+00:00"
    if len(text) == 5 and text[0] in "+-" and text[1:].isdigit():
        return f"{text[:3]}:{text[3:]}"
    if len(text) == 6 and text[0] in "+-" and text[3] == ":" and text[1:3].isdigit() and text[4:].isdigit():
        return text
    return None


def _has_datetime_offset(text: str) -> bool:
    candidate = text.strip().upper()
    if candidate.endswith("Z"):
        return True
    tail = candidate[-6:]
    return len(tail) == 6 and tail[0] in "+-" and tail[3] == ":" and tail[1:3].isdigit() and tail[4:].isdigit()


def _coerce_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def likely_supported_by_pillow(path: Path) -> bool:
    mime, _ = mimetypes.guess_type(path.name)
    return bool(mime and mime.startswith("image/"))
