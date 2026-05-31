from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from .geo import Bounds, bounds_from_values


DEFAULT_MAP_DATASET_CATALOG_ROOT = "https://map-dataset.cadis.dev/releases"


@dataclass(frozen=True)
class BaseMap:
    image: Image.Image
    bounds: Bounds
    scene_id: str
    scene_version: str | None
    metadata: dict[str, Any]


class CadisMapRenderEngine:
    def __init__(
        self,
        *,
        scene_id: str,
        output_root: Path,
        cache_root: Path | None = None,
        catalog_root: str = DEFAULT_MAP_DATASET_CATALOG_ROOT,
        dataset_root: Path | None = None,
    ) -> None:
        self.scene_id = scene_id
        self.output_root = output_root
        self.cache_root = cache_root
        self.catalog_root = catalog_root
        self.dataset_root = dataset_root

    def scene_metadata(self) -> dict[str, Any]:
        client = self._client()
        for scene in client.list_scenes():
            if _scene_id_matches(str(scene.get("scene_id", "")), self.scene_id):
                return scene
        raise RuntimeError(f"scene_id is not available from cadis-map-render dataset source: {self.scene_id!r}")

    def render_base_map(
        self,
        *,
        map_style: str,
        width: int,
        height: int,
        crop_bounds: Bounds | None = None,
    ) -> BaseMap:
        raise RuntimeError(
            "TravelSpark requires cadis-map-render basemap-only or spark-night support before "
            "the official engine path can render GIFs. The app-layer scaffold is ready; implement "
            "the renderer capability in cadis-map-render next."
        )

    def _client(self):
        try:
            from cadis_map_render import CadisMapRenderClient
        except Exception as exc:
            raise RuntimeError(
                "cadis-map-render is not installed. Run ./install.sh or place a pinned "
                "cadis_map_render wheel under wheels/."
            ) from exc
        if self.dataset_root is not None:
            return CadisMapRenderClient.from_file_dataset(
                self.dataset_root,
                output_root=self.output_root,
                cache_root=self.cache_root,
            )
        return CadisMapRenderClient.from_cdn_catalog(
            self.catalog_root,
            scene_id=self.scene_id,
            cache_root=self.cache_root,
            output_root=self.output_root,
        )


def scene_bounds(scene: dict[str, Any]) -> Bounds:
    bounds = scene.get("bounds")
    if not isinstance(bounds, list | tuple):
        raise RuntimeError("selected scene metadata does not include bounds")
    return bounds_from_values(bounds)


def scene_country_iso(scene_id: str) -> str | None:
    normalized = scene_id.strip().lower()
    if len(normalized) == 2 and normalized.isalpha():
        return normalized.upper()
    if normalized.startswith("country_") and len(normalized) == len("country_") + 2:
        return normalized[-2:].upper()
    if normalized.startswith("iso2_") and len(normalized) == len("iso2_") + 2:
        return normalized[-2:].upper()
    return None


def _scene_id_matches(public_scene_id: str, requested_scene_id: str) -> bool:
    return public_scene_id.strip().lower() == requested_scene_id.strip().lower()
