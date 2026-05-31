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
source .venv/bin/activate
travelspark /path/to/photos --scene-id world_8192 --output travel.gif
```

Windows PowerShell:

```powershell
.\install.ps1
.venv\Scripts\Activate.ps1
travelspark C:\path\to\photos --scene-id world_8192 --output travel.gif
```

The install scripts create a repo-local `.venv`. Activating that environment
must be done in your current shell after the installer exits; otherwise the
`travelspark` command will not be on `PATH`. You can also run without activating:

```bash
.venv/bin/travelspark /path/to/photos --scene-id world_8192 --output travel.gif
```

The installers prefer pinned wheels from `wheels/` when present. This keeps the
repo usable as a one-stop side-project package while leaving `cadis` and
`cadis-map-render` as independent upstream projects.

Vendored wheels are pinned in `requirements.lock.txt`:

- `cadis==0.9.0`
- `cadis-map-render==0.3.28`
- `cadis-travel-spark==0.1.0`
