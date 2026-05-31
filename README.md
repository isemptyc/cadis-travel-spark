# TravelSpark

TravelSpark turns a local photo folder into an animated travel map GIF.

The application layer owns photo scanning, EXIF GPS extraction, point
filtering, animation timing, and GIF encoding. CADIS map rendering is expected
to come from `cadis-map-render`; CADIS country lookup is used as an optional
preflight/filter helper.

## Contract

```text
PathToPhotos + SceneName + MapStyle + Options -> GIF
```

Example:

```bash
travelspark /path/to/photos \
  --scene-id world_8192 \
  --map-style spark-night \
  --output travel.gif
```

## Install

Mac/Linux:

```bash
./install.sh
```

Windows PowerShell:

```powershell
.\install.ps1
```

The installers prefer pinned wheels from `wheels/` when present. This keeps the
repo usable as a one-stop side-project package while leaving `cadis` and
`cadis-map-render` as independent upstream projects.

Vendored wheels are pinned in `requirements.lock.txt`:

- `cadis==0.9.0`
- `cadis-map-render==0.3.28`

## Dataset

The default CADIS map dataset catalog root is:

```text
https://map-dataset.cadis.dev/releases
```

`cadis-map-render` owns downloading, caching, extracting, and validating scene
packages from that catalog. By default it stores downloaded map datasets in the
OS user cache directory. Use `--cache-root` only when you want to override that
engine cache location.
