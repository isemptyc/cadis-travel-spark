from pathlib import Path

import pytest

from travelspark.exif import PhotoPoint, extract_photo_points


def test_extract_photo_points_auto_prefers_exiftool_then_pillow_fallback(tmp_path: Path, monkeypatch):
    files = [tmp_path / "a.jpg", tmp_path / "b.jpg"]
    for file in files:
        file.write_bytes(b"")
    calls = []

    monkeypatch.setattr("travelspark.exif.find_photo_files", lambda folder: files)
    monkeypatch.setattr("travelspark.exif.shutil.which", lambda name: "/usr/bin/exiftool")

    def fake_exiftool(paths, *, skip_paths, progress):
        calls.append(("exiftool", list(paths), set(skip_paths)))
        return [PhotoPoint(files[0], 25.0, 121.0)]

    def fake_pillow(paths, *, progress):
        calls.append(("pillow", list(paths)))
        return [PhotoPoint(files[1], 35.0, 139.0)]

    monkeypatch.setattr("travelspark.exif._extract_with_exiftool", fake_exiftool)
    monkeypatch.setattr("travelspark.exif._extract_with_pillow", fake_pillow)

    points = extract_photo_points(tmp_path, use_exiftool="auto")

    assert [(point.path, point.latitude, point.longitude) for point in points] == [
        (files[0], 25.0, 121.0),
        (files[1], 35.0, 139.0),
    ]
    assert calls == [
        ("exiftool", files, set()),
        ("pillow", [files[1]]),
    ]


def test_extract_photo_points_auto_uses_pillow_when_exiftool_missing(tmp_path: Path, monkeypatch):
    file = tmp_path / "a.jpg"
    file.write_bytes(b"")
    monkeypatch.setattr("travelspark.exif.find_photo_files", lambda folder: [file])
    monkeypatch.setattr("travelspark.exif.shutil.which", lambda name: None)
    monkeypatch.setattr(
        "travelspark.exif._extract_with_pillow",
        lambda paths, *, progress: [PhotoPoint(file, 25.0, 121.0)],
    )

    points = extract_photo_points(tmp_path, use_exiftool="auto")

    assert points == [PhotoPoint(file, 25.0, 121.0)]


def test_extract_photo_points_yes_requires_exiftool(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("travelspark.exif.find_photo_files", lambda folder: [])
    monkeypatch.setattr("travelspark.exif.shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="exiftool is required"):
        extract_photo_points(tmp_path, use_exiftool="yes")
