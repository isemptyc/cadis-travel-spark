from pathlib import Path

import pytest

from travelspark.exif import PhotoPoint, _parse_datetime, _run_exiftool, extract_photo_points


def test_extract_photo_points_auto_uses_exiftool_quick_full_then_pillow_fallback(tmp_path: Path, monkeypatch):
    files = [tmp_path / "a.jpg", tmp_path / "b.jpg", tmp_path / "c.jpg"]
    for file in files:
        file.write_bytes(b"")
    calls = []

    monkeypatch.setattr("travelspark.exif.find_photo_files", lambda folder: files)
    monkeypatch.setattr("travelspark.exif.shutil.which", lambda name: "/usr/bin/exiftool")

    def fake_exiftool(paths, *, skip_paths, progress, mode):
        calls.append(("exiftool", mode, list(paths), set(skip_paths)))
        if mode == "quick":
            return [PhotoPoint(files[0], 25.0, 121.0)]
        return [PhotoPoint(files[1], 35.0, 139.0)]

    def fake_pillow(paths, *, progress):
        calls.append(("pillow", list(paths)))
        return [PhotoPoint(files[2], 60.0, 24.0)]

    monkeypatch.setattr("travelspark.exif._extract_with_exiftool", fake_exiftool)
    monkeypatch.setattr("travelspark.exif._extract_with_pillow", fake_pillow)

    points = extract_photo_points(tmp_path, use_exiftool="auto")

    assert [(point.path, point.latitude, point.longitude) for point in points] == [
        (files[0], 25.0, 121.0),
        (files[1], 35.0, 139.0),
        (files[2], 60.0, 24.0),
    ]
    assert calls == [
        ("exiftool", "quick", files, set()),
        ("exiftool", "full", [files[1], files[2]], {files[0].resolve()}),
        ("pillow", [files[2]]),
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


def test_run_exiftool_quick_mode_uses_fast2_and_full_mode_does_not(tmp_path: Path, monkeypatch):
    file = tmp_path / "a.jpg"
    file.write_bytes(b"")
    commands = []

    class Result:
        returncode = 0
        stdout = '[{"SourceFile":"%s","GPSLatitude":25,"GPSLongitude":121}]' % str(file)

    def fake_run(command, *, check, capture_output, text):
        commands.append(command)
        return Result()

    monkeypatch.setattr("travelspark.exif.subprocess.run", fake_run)

    _run_exiftool([file], mode="quick")
    _run_exiftool([file], mode="full")

    assert "-fast2" in commands[0]
    assert "-fast2" not in commands[1]


def test_parse_datetime_uses_offset_time_original():
    parsed = _parse_datetime("2024:09:10 12:34:56.789", offset="+0800")

    assert parsed is not None
    assert parsed.isoformat() == "2024-09-10T12:34:56.789000+08:00"
