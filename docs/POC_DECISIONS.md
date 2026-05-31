# TravelSpark PoC Decisions

## Status

TravelSpark is in PoC stage. The goal is to prove the product workflow and
style boundary before investing in layer hand-off or richer renderer contracts.

## Product Framing

TravelSpark is a semantic travel presentation renderer.

```text
PathToPhotos + SceneID + MapStyle + Storyboard + Options -> JPEG/PNG/GIF
```

The output format is an export decision:

- One-frame storyboard can export `.jpg`, `.jpeg`, `.png`, or `.gif`.
- Multi-frame storyboard exports `.gif` for now.

## Ownership

`cadis-map-render` owns stylish still map rendering:

- map dataset access
- scene projection
- CADIS map style interpretation
- static marks and activations
- still map output

TravelSpark owns semantic presentation:

- photo scanning
- EXIF GPS extraction
- scene filtering
- Director/storyboard policy
- optional presentation effects
- JPEG/PNG/GIF export

## Storyboard v0

The PoC storyboard names are:

- `all-points`: one presentation frame containing all kept GPS points.
- `ambient-spark`: animated visual atmosphere with quiet deterministic spark twinkles.
- `timeline`: animated timeline ordered by photo timestamp/path.
- `cluster`: animated cluster pulse.
- `constellation`: animated point shimmer.

The first built-in visual preset is:

- `spark-drift`: maps to `ambient-spark`, defaults to GIF, and aims for a
  quiet night-sky sparkle feeling without strong timeline semantics.

The legacy `--mode` flag remains as a temporary alias for animated storyboard
names. New usage should prefer `--storyboard`.

## Effects

The PoC effect modes are:

- `none`: use the CADIS-rendered marked map directly. This is the style-fidelity path.
- `glow`: use TravelSpark's current presentation glow layer. This is experimental.

Animated storyboards currently require:

```text
--effect glow
--output *.gif
```

This is intentional. Layer hand-off is deferred, so TravelSpark cannot yet ask
`cadis-map-render` for a layered still package and insert effects at a formal
slot.

## Style

The public style input is `--map-style`.

`spark-night` resolves to the real CADIS atlas-night style:

```text
spark-night -> memory_atlas_night_v1
```

`cadis-map-render` owns the canonical CADIS map style. TravelSpark may derive
presentation effect defaults from the selected style, but it should not be the
source of truth for map style values.

The optional `--style` JSON path is an advanced/debug escape hatch. It should
not be required for normal TravelSpark usage.

## Deferred

Layer hand-off is deferred until the PoC product workflow is validated.

The expected future direction is:

```text
cadis-map-render -> styled layer package + insertion slots
TravelSpark Director -> semantic effect layers
TravelSpark Exporter -> JPEG/PNG/GIF/other
```

No API should assume this contract exists yet.
