# TravelSpark

TravelSpark turns a local photo folder into a semantic travel presentation.

The application layer owns photo scanning, EXIF GPS extraction, point
filtering, storyboard timing, presentation effects, and output export. CADIS
map rendering is expected to come from `cadis-map-render`; CADIS country lookup
is used as an optional preflight/filter helper.

GPS extraction defaults to `--use-exiftool auto`: TravelSpark prefers
`exiftool` when it is available. It first runs an EXIFTool quick pass
(`-fast2`) for GPS and datetime tags only, then runs full EXIFTool only for
files missed by quick mode, and finally falls back to Pillow for any remaining
files that EXIFTool did not return at all or when `exiftool` is not on `PATH`.
Files that EXIFTool successfully reads but that simply do not contain GPS are
not sent through the slower Pillow fallback. Use `--use-exiftool yes` to
require `exiftool`, or `--use-exiftool no` to force Pillow-only parsing.

Scene filtering is bounds-first for speed. In `--country-filter auto`,
TravelSpark prefers CADIS `lookup_many()` for country-scene filtering. When the
optional native CGD module is installed, CADIS automatically uses its Rust
world pass through that batch API. TravelSpark sends those lookups in bounded
50,000-point batches, matching EONA's CADIS integration batch size. If an older
CADIS build has only scalar `lookup()`, TravelSpark still uses scalar country
lookup for small in-bounds sets and skips it for very large auto-filtered sets;
pass `--country-filter yes` to force scalar strict filtering in that fallback
case.

## Contract

```text
PathToPhotos + SceneName + MapStyle + Storyboard + Options -> JPEG/PNG/GIF/timeline-scene
```

Example:

```bash
travelspark /path/to/photos \
  --scene-id world_8192 \
  --map-style spark-night \
  --storyboard all-points \
  --effect none \
  --output travel.jpg
```

Visual-first online preview preset:

```bash
travelspark /path/to/photos \
  --scene-id world_8192 \
  --map-style spark-night \
  --storyboard-preset spark-drift
```

This writes `timeline-scene.json`, `timeline-scene.html`, and a local basemap
asset folder by default. Open the HTML file to play, pause, and scrub the
ambient spark timeline without GIF palette and frame-delay limits.

Optional GIF export:

```bash
travelspark /path/to/photos \
  --scene-id world_8192 \
  --map-style spark-night \
  --storyboard-preset spark-drift \
  --output travel.gif
```

PoC framing:

- `cadis-map-render` owns stylish still-image rendering.
- TravelSpark owns the Director/storyboard and export workflow.
- `--effect none` uses the CADIS-rendered marked still frame directly.
- `--effect glow` uses TravelSpark's current presentation effect layer.
- `--storyboard-preset spark-drift` creates a quiet night-sky sparkle timeline.
- Online preview is the default visual-preset presentation; GIF is an explicit
  export target when `--output *.gif` is provided.

## Install

Mac/Linux:

```bash
./install.sh
source .venv/bin/activate
travelspark /path/to/photos --scene-id world_8192 --output travel.jpg
```

Windows PowerShell:

```powershell
.\install.ps1
.venv\Scripts\Activate.ps1
travelspark C:\path\to\photos --scene-id world_8192 --output travel.jpg
```

The install scripts create a repo-local `.venv`. Activating that environment
must be done in your current shell after the installer exits; otherwise the
`travelspark` command will not be on `PATH`. You can also run without activating:

```bash
.venv/bin/travelspark /path/to/photos --scene-id world_8192 --output travel.jpg
```

The installers prefer pinned wheels from `wheels/` when present. This keeps the
repo usable as a one-stop side-project package while leaving `cadis` and
`cadis-map-render` as independent upstream projects. For CPython 3.12 on
Darwin arm64 or Linux amd64, the installers also select the matching vendored
`cadis_native_cgd` wheel from `wheels/darwin-arm64/` or `wheels/linux-amd64/` so
CADIS can use its Rust CGD world pass.

To update an existing activated `.venv` after `git pull`, reinstall the
TravelSpark wheel without touching already installed dependencies:

```bash
python -m pip install --force-reinstall --no-deps wheels/cadis_map_render-0.3.32-py3-none-any.whl wheels/cadis_travel_spark-0.1.22-py3-none-any.whl
```

If Pillow was accidentally reinstalled into a broken state, repair it first:

```bash
python -m pip install --force-reinstall --no-cache-dir "Pillow>=10,<12.2"
python -m pip install --force-reinstall --no-deps wheels/cadis_map_render-0.3.32-py3-none-any.whl wheels/cadis_travel_spark-0.1.22-py3-none-any.whl
```

Vendored wheels are pinned in `requirements.lock.txt`:

- `cadis==0.9.0`
- `cadis-map-render==0.3.32`
- `cadis-native-cgd==0.1.0` for CPython 3.12 Darwin arm64 / Linux amd64
- `cadis-travel-spark==0.1.22`
