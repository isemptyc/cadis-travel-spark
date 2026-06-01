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
        style_profile: dict[str, Any] | None = None,
    ) -> BaseMap:
        client = self._client()
        payload: dict[str, Any] = {
            "scene_id": self.scene_id,
            "style_id": map_style,
        }
        if style_profile is not None:
            payload["style_profile"] = style_profile
        if crop_bounds is not None:
            payload["crop_bounds"] = [
                crop_bounds.min_lon,
                crop_bounds.min_lat,
                crop_bounds.max_lon,
                crop_bounds.max_lat,
            ]
        try:
            result = client.render_base_map(payload)
        except AttributeError as exc:
            raise RuntimeError(
                "cadis-map-render is installed, but it is too old for TravelSpark. "
                "Install the pinned cadis_map_render wheel from this repo."
            ) from exc

        image_path = result.get("image_path")
        if not isinstance(image_path, str) or not image_path:
            raise RuntimeError("cadis-map-render did not return a base map image_path")
        bounds = result.get("bounds")
        if not isinstance(bounds, list | tuple):
            raise RuntimeError("cadis-map-render did not return base map bounds")

        image = Image.open(image_path).convert("RGB")
        return BaseMap(
            image=image,
            bounds=bounds_from_values(bounds),
            scene_id=str(result.get("scene_id") or self.scene_id),
            scene_version=str(result["scene_version"]) if result.get("scene_version") is not None else None,
            metadata={
                "source": "cadis-map-render",
                "render_type": result.get("render_type"),
                "scene_id": result.get("scene_id"),
                "scene_version": result.get("scene_version"),
                "style_id": result.get("style_id"),
                "cadis_style_id": result.get("cadis_style_id"),
                "bounds": list(bounds),
                "projection": result.get("projection"),
                "image_path": image_path,
            },
        )

    def render_marked_map(
        self,
        *,
        points: list[Any],
        map_style: str,
        width: int,
        height: int,
        crop_bounds: Bounds | None = None,
        style_profile: dict[str, Any] | None = None,
    ) -> BaseMap:
        client = self._client()
        payload: dict[str, Any] = {
            "scene_id": self.scene_id,
            "style_id": map_style,
            "points": [
                {
                    "lat": float(point.latitude),
                    "lon": float(point.longitude),
                    "density": 1,
                }
                for point in points
            ],
        }
        if style_profile is not None:
            payload["style_profile"] = style_profile
        if crop_bounds is not None:
            payload["crop_bounds"] = [
                crop_bounds.min_lon,
                crop_bounds.min_lat,
                crop_bounds.max_lon,
                crop_bounds.max_lat,
            ]
        result = client.render_map(payload)
        render_id = result.get("render_id")
        if not isinstance(render_id, str) or not render_id:
            raise RuntimeError("cadis-map-render did not return a render_id")
        image_path = self.output_root / "renders" / render_id / "map.png"
        if not image_path.exists():
            raise RuntimeError(f"cadis-map-render output image was not found: {image_path}")
        image = Image.open(image_path).convert("RGB")
        bounds = crop_bounds or self._scene_bounds_from_result(result)
        return BaseMap(
            image=image,
            bounds=bounds,
            scene_id=str(result.get("scene_id") or self.scene_id),
            scene_version=str(result["scene_version"]) if result.get("scene_version") is not None else None,
            metadata={
                "source": "cadis-map-render",
                "render_type": result.get("render_type"),
                "scene_id": result.get("scene_id"),
                "scene_version": result.get("scene_version"),
                "style_id": result.get("style_id"),
                "cadis_style_id": result.get("cadis_style_id"),
                "activation_mode": result.get("activation_mode"),
                "image_path": str(image_path),
            },
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

    def _scene_bounds_from_result(self, result: dict[str, Any]) -> Bounds:
        for scene in self._client().list_scenes():
            if _scene_id_matches(str(scene.get("scene_id", "")), str(result.get("scene_id") or self.scene_id)):
                return scene_bounds(scene)
        raise RuntimeError("rendered scene metadata does not include bounds")


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
