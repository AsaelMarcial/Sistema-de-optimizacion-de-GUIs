from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field, replace
import re
from typing import Any, Iterable, Iterator, Mapping, Self

from engine.domain.data.css_properties import CssColorRole, get_css_property
from engine.domain.data.web_colors import nearest_web_color
from engine.adapters.color_service import color_registry
from engine.domain.enums.types.color import (
    ColorConfirmationStatus,
    ColorFamilyType,
)

_ACHROMATIC_CHROMA_THRESHOLD = 8.0
_PIXEL_CONFIRMATION_DELTA_E_THRESHOLD = 6.0
_COLOR_ID_RE = re.compile(r"^color-(\d+)$")


def _coerce_color_family_type(
    value: ColorFamilyType | str | None,
) -> ColorFamilyType:
    if isinstance(value, ColorFamilyType):
        return value
    normalized = str(value or ColorFamilyType.CHROMATIC.value).strip().lower()
    return ColorFamilyType(normalized)


def _coerce_confirmation_status(
    value: ColorConfirmationStatus | str | None,
) -> ColorConfirmationStatus:
    if isinstance(value, ColorConfirmationStatus):
        return value
    normalized = str(value or ColorConfirmationStatus.SEMANTIC_ONLY.value).strip().lower()
    return ColorConfirmationStatus(normalized)


@dataclass(frozen=True, slots=True)
class TagUsageModel:
    tag: str
    count: int

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            tag=str(payload.get("tag") or ""),
            count=int(payload.get("count") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "count": self.count}


@dataclass(frozen=True, slots=True)
class PropertyUsageModel:
    property_name: str
    total_count: int
    tags: tuple[TagUsageModel, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            property_name=str(payload.get("property") or payload.get("property_name") or ""),
            total_count=int(payload.get("total_count") or 0),
            tags=tuple(
                TagUsageModel.build(item)
                for item in (payload.get("tags") or ())
                if isinstance(item, Mapping)
            ),
        )

    def __iter__(self) -> Iterator[TagUsageModel]:
        return iter(self.tags)

    def to_dict(self) -> dict[str, Any]:
        return {
            "property": self.property_name,
            "total_count": self.total_count,
            "tags": [item.to_dict() for item in self.tags],
        }


@dataclass(frozen=True, slots=True)
class ColorUsageModel:
    tag: str
    property_name: str
    count: int

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            tag=str(payload.get("tag") or ""),
            property_name=str(payload.get("property") or payload.get("property_name") or ""),
            count=int(payload.get("count") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "property": self.property_name,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class ObservedColorRoleModel:
    role: str
    count: int
    node_ids: tuple[str, ...] = field(default_factory=tuple)
    sample_selectors: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            role=str(payload.get("role") or "").strip(),
            count=int(payload.get("count") or 0),
            node_ids=tuple(
                str(item).strip()
                for item in (payload.get("node_ids") or ())
                if str(item).strip()
            ),
            sample_selectors=tuple(
                str(item).strip()
                for item in (payload.get("sample_selectors") or ())
                if str(item).strip()
            ),
        )

    def merge(self, other: Self) -> Self:
        merged_node_ids = tuple(
            sorted({*self.node_ids, *other.node_ids})
        )
        merged_selectors = tuple(
            list(dict.fromkeys([*self.sample_selectors, *other.sample_selectors]).keys())[:5]
        )
        merged_count = len(merged_node_ids) if merged_node_ids else self.count + other.count
        return cls(
            role=self.role or other.role,
            count=merged_count,
            node_ids=merged_node_ids,
            sample_selectors=merged_selectors,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "role": self.role,
            "count": self.count,
        }
        if self.node_ids:
            payload["node_ids"] = list(self.node_ids)
        if self.sample_selectors:
            payload["sample_selectors"] = list(self.sample_selectors)
        return payload


@dataclass(frozen=True, slots=True)
class PixelColorRecord:
    color: tuple[int, int, int]
    count: int
    color_id: str | None = None
    percentage: float | None = None
    alpha: float | None = None
    source: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> Self:
        color = tuple(int(channel) for channel in payload.get("color", ()))  # type: ignore[arg-type]
        if len(color) != 3:
            raise ValueError(f"Pixel color invalido: {payload!r}")
        return cls(
            color=color,  # type: ignore[arg-type]
            count=int(payload.get("count", 0)),
            color_id=str(payload["color_id"]) if payload.get("color_id") is not None else None,
            percentage=(
                round(float(payload["percentage"]), 4)
                if payload.get("percentage") is not None
                else None
            ),
            alpha=float(payload["alpha"]) if payload.get("alpha") is not None else None,
            source=str(payload["source"]) if payload.get("source") is not None else None,
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def build_many(
        cls,
        payloads: Mapping[str, object]
        | list[Mapping[str, object]]
        | tuple[Mapping[str, object], ...]
        | None,
    ) -> tuple[Self, ...]:
        if not payloads:
            return ()
        return tuple(cls.from_mapping(item) for item in payloads)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "color": [int(channel) for channel in self.color],
            "count": int(self.count),
        }
        if self.color_id is not None:
            payload["color_id"] = self.color_id
        if self.percentage is not None:
            payload["percentage"] = self.percentage
        if self.alpha is not None:
            payload["alpha"] = round(self.alpha, 4)
        if self.source is not None:
            payload["source"] = self.source
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True, slots=True)
class UnmatchedVisualPixelsModel:
    count: int = 0
    percentage: float = 0.0
    distinct_clusters: int = 0

    @classmethod
    def build(cls, payload: Mapping[str, Any] | None = None) -> Self:
        payload = payload or {}
        return cls(
            count=int(payload.get("count") or 0),
            percentage=round(float(payload.get("percentage") or 0.0), 4),
            distinct_clusters=int(payload.get("distinct_clusters") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "percentage": self.percentage,
            "distinct_clusters": self.distinct_clusters,
        }


@dataclass(frozen=True, slots=True)
class DisplayPixelFrequenciesModel:
    matched_inventory_colors: tuple[PixelColorRecord, ...] = field(default_factory=tuple)
    unmatched_visual_pixels: UnmatchedVisualPixelsModel = field(
        default_factory=UnmatchedVisualPixelsModel
    )
    total_pixels_considered: int = 0
    excluded_regions_summary: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def build(cls, payload: Mapping[str, Any] | None = None) -> Self:
        payload = payload or {}
        return cls(
            matched_inventory_colors=tuple(
                PixelColorRecord.from_mapping(item)
                for item in (payload.get("matched_inventory_colors") or ())
                if isinstance(item, Mapping)
            ),
            unmatched_visual_pixels=UnmatchedVisualPixelsModel.build(
                payload.get("unmatched_visual_pixels")
                if isinstance(payload.get("unmatched_visual_pixels"), Mapping)
                else None
            ),
            total_pixels_considered=int(payload.get("total_pixels_considered") or 0),
            excluded_regions_summary=dict(payload.get("excluded_regions_summary") or {}),
        )

    def __iter__(self) -> Iterator[PixelColorRecord]:
        return iter(self.matched_inventory_colors)

    def __len__(self) -> int:
        return len(self.matched_inventory_colors)

    def to_rows(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.matched_inventory_colors]

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched_inventory_colors": self.to_rows(),
            "unmatched_visual_pixels": self.unmatched_visual_pixels.to_dict(),
            "total_pixels_considered": self.total_pixels_considered,
            "excluded_regions_summary": dict(self.excluded_regions_summary),
        }


@dataclass(frozen=True, slots=True)
class ColorInventoryEntry:
    color_id: str
    value: str
    hex_value: str
    rgb: tuple[int, int, int]
    alpha: float
    hct: tuple[float, float, float]
    usage_count: int
    node_ids: tuple[str, ...] = field(default_factory=tuple)
    usage: tuple[ColorUsageModel, ...] = field(default_factory=tuple)
    observed_usage_count: int = 0
    observed_roles: tuple[ObservedColorRoleModel, ...] = field(default_factory=tuple)
    nearest_web_color: str | None = None
    nearest_web_color_distance: float | None = None
    declared_in_snapshot: bool = True
    added_from_pixel_evidence: bool = False
    display_pixel_count: int = 0
    display_pixel_percentage: float | None = None
    clustered_from_display_pixels: bool = False
    mapped_palette_id: str | None = None
    mapped_tone: int | None = None
    mapped_tone_rgb: tuple[int, int, int] | None = None
    mapped_tone_distance: float | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        value = str(payload.get("value") or "").strip()
        rgb = color_registry.format_color(value, "rgb")
        nearest_match = nearest_web_color(rgb)
        node_ids = tuple(
            str(item).strip()
            for item in (payload.get("node_ids") or ())
            if str(item).strip()
        )
        observed_roles = tuple(
            ObservedColorRoleModel.build(item)
            for item in (payload.get("observed_roles") or ())
            if isinstance(item, Mapping)
        )
        observed_node_ids = {
            node_id
            for role in observed_roles
            for node_id in role.node_ids
        }
        return cls(
            color_id=str(payload.get("color_id") or ""),
            value=value,
            hex_value=color_registry.format_color(value, "hex"),
            rgb=rgb,
            alpha=color_registry.alpha_of(value),
            hct=color_registry.hct_of(value),
            usage_count=int(payload.get("usage_count") or len(node_ids) or 0),
            node_ids=node_ids,
            usage=tuple(
                ColorUsageModel.build(item)
                for item in (payload.get("usage") or ())
                if isinstance(item, Mapping)
            ),
            observed_usage_count=(
                int(payload.get("observed_usage_count") or len(observed_node_ids) or 0)
            ),
            observed_roles=observed_roles,
            nearest_web_color=nearest_match.color_name,
            nearest_web_color_distance=round(nearest_match.distance, 4),
            declared_in_snapshot=bool(payload.get("declared_in_snapshot", True)),
            added_from_pixel_evidence=bool(payload.get("added_from_pixel_evidence", False)),
            display_pixel_count=int(payload.get("display_pixel_count") or 0),
            display_pixel_percentage=(
                round(float(payload["display_pixel_percentage"]), 4)
                if payload.get("display_pixel_percentage") is not None
                else None
            ),
            clustered_from_display_pixels=bool(
                payload.get("clustered_from_display_pixels", False)
            ),
            mapped_palette_id=(
                str(payload["mapped_palette_id"])
                if payload.get("mapped_palette_id") is not None
                else None
            ),
            mapped_tone=(
                int(payload["mapped_tone"])
                if payload.get("mapped_tone") is not None
                else None
            ),
            mapped_tone_rgb=(
                tuple(int(channel) for channel in payload.get("mapped_tone_rgb", ()))  # type: ignore[arg-type]
                if payload.get("mapped_tone_rgb") is not None
                else None
            ),
            mapped_tone_distance=(
                round(float(payload["mapped_tone_distance"]), 4)
                if payload.get("mapped_tone_distance") is not None
                else None
            ),
        )

    def signature(self) -> tuple[str, float]:
        return self.hex_value, round(self.alpha, 4)

    def merge(self, other: Self) -> Self:
        merged_usage: dict[tuple[str, str], int] = defaultdict(int)
        for usage_item in (*self.usage, *other.usage):
            merged_usage[(usage_item.tag, usage_item.property_name)] += usage_item.count
        merged_usage_models = tuple(
            ColorUsageModel(tag=tag, property_name=property_name, count=count)
            for (tag, property_name), count in sorted(merged_usage.items())
        )
        merged_node_ids = tuple(sorted({*self.node_ids, *other.node_ids}))
        merged_roles: dict[str, ObservedColorRoleModel] = {}
        for observed_role in (*self.observed_roles, *other.observed_roles):
            if observed_role.role in merged_roles:
                merged_roles[observed_role.role] = merged_roles[observed_role.role].merge(
                    observed_role
                )
            else:
                merged_roles[observed_role.role] = observed_role
        merged_observed_roles = tuple(
            merged_roles[key]
            for key in sorted(merged_roles)
        )
        observed_node_ids = {
            node_id
            for role in merged_observed_roles
            for node_id in role.node_ids
        }
        return replace(
            self,
            usage_count=(
                len(merged_node_ids)
                if merged_node_ids
                else self.usage_count + other.usage_count
            ),
            node_ids=merged_node_ids,
            usage=merged_usage_models,
            observed_usage_count=(
                len(observed_node_ids)
                if observed_node_ids
                else self.observed_usage_count + other.observed_usage_count
            ),
            observed_roles=merged_observed_roles,
            declared_in_snapshot=self.declared_in_snapshot or other.declared_in_snapshot,
            added_from_pixel_evidence=(
                self.added_from_pixel_evidence or other.added_from_pixel_evidence
            ),
            display_pixel_count=self.display_pixel_count + other.display_pixel_count,
            display_pixel_percentage=(
                round(
                    (self.display_pixel_percentage or 0.0)
                    + (other.display_pixel_percentage or 0.0),
                    4,
                )
                if self.display_pixel_percentage is not None
                or other.display_pixel_percentage is not None
                else None
            ),
            clustered_from_display_pixels=(
                self.clustered_from_display_pixels or other.clustered_from_display_pixels
            ),
        )

    def property_names(self) -> tuple[str, ...]:
        return tuple(sorted({item.property_name for item in self.usage}))

    def tag_names(self) -> tuple[str, ...]:
        return tuple(sorted({item.tag for item in self.usage}))

    def with_palette_mapping(
        self,
        *,
        palette_id: str,
        tone: int,
        tone_rgb: tuple[int, int, int],
        tone_distance: float,
    ) -> Self:
        return replace(
            self,
            mapped_palette_id=palette_id,
            mapped_tone=tone,
            mapped_tone_rgb=tone_rgb,
            mapped_tone_distance=round(tone_distance, 4),
        )

    def with_display_evidence(
        self,
        *,
        pixel_count: int,
        pixel_percentage: float | None = None,
        clustered: bool = False,
    ) -> Self:
        return replace(
            self,
            display_pixel_count=int(pixel_count),
            display_pixel_percentage=(
                round(float(pixel_percentage), 4)
                if pixel_percentage is not None
                else self.display_pixel_percentage
            ),
            clustered_from_display_pixels=clustered,
        )

    def to_palette_entry(self) -> dict[str, Any]:
        payload = {
            "color_id": self.color_id,
            "value": self.value,
            "usage_count": self.usage_count,
        }
        if self.usage:
            payload["usage"] = [item.to_dict() for item in self.usage]
        if self.node_ids:
            payload["node_ids"] = list(self.node_ids)
        return payload

    def to_dict(self) -> dict[str, Any]:
        payload = self.to_palette_entry()
        payload["hex_value"] = self.hex_value
        payload["rgb"] = list(self.rgb)
        payload["alpha"] = self.alpha
        payload["hct"] = list(self.hct)
        if self.nearest_web_color is not None:
            payload["nearest_web_color"] = self.nearest_web_color
        if self.nearest_web_color_distance is not None:
            payload["nearest_web_color_distance"] = self.nearest_web_color_distance
        if not self.declared_in_snapshot:
            payload["declared_in_snapshot"] = False
        if self.added_from_pixel_evidence:
            payload["added_from_pixel_evidence"] = True
        if self.observed_usage_count:
            payload["observed_usage_count"] = self.observed_usage_count
        if self.observed_roles:
            payload["observed_roles"] = [item.to_dict() for item in self.observed_roles]
        if self.display_pixel_count:
            payload["display_pixel_count"] = self.display_pixel_count
        if self.display_pixel_percentage is not None and self.display_pixel_percentage > 0:
            payload["display_pixel_percentage"] = self.display_pixel_percentage
        if self.clustered_from_display_pixels:
            payload["clustered_from_display_pixels"] = True
        if self.mapped_palette_id is not None:
            payload["mapped_palette_id"] = self.mapped_palette_id
        if self.mapped_tone is not None:
            payload["mapped_tone"] = self.mapped_tone
        if self.mapped_tone_rgb is not None:
            payload["mapped_tone_rgb"] = list(self.mapped_tone_rgb)
        if self.mapped_tone_distance is not None:
            payload["mapped_tone_distance"] = self.mapped_tone_distance
        return payload


@dataclass(frozen=True, slots=True)
class ColorInventoryModel:
    entries: tuple[ColorInventoryEntry, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payloads: Iterable[ColorInventoryEntry | Mapping[str, Any]] | None) -> Self:
        if not payloads:
            return cls()

        normalized_payloads = tuple(payloads)
        deduped: dict[tuple[str, float], ColorInventoryEntry] = {}
        generated_index = max(
            (
                int(color_id.split("-")[-1])
                for color_id in (
                    (
                        str(payload.color_id)
                        if isinstance(payload, ColorInventoryEntry)
                        else str(payload.get("color_id") or "")
                    )
                    for payload in normalized_payloads
                )
                if color_id.startswith("color-") and color_id.split("-")[-1].isdigit()
            ),
            default=0,
        )
        for payload in normalized_payloads:
            entry = payload if isinstance(payload, ColorInventoryEntry) else ColorInventoryEntry.build(payload)
            if not entry.color_id:
                generated_index += 1
                entry = replace(entry, color_id=f"color-{generated_index}")
            signature = entry.signature()
            if signature in deduped:
                deduped[signature] = deduped[signature].merge(entry)
            else:
                deduped[signature] = entry

        ordered_entries = tuple(
            sorted(
                deduped.values(),
                key=lambda item: (_color_id_sort_key(item.color_id), item.hex_value, item.alpha),
            )
        )
        return cls(entries=ordered_entries)

    @classmethod
    def build_from_usage_map(cls, palette_usage: Mapping[str, Mapping[str, Any]]) -> Self:
        payloads = []
        for index, (value, entry) in enumerate(palette_usage.items(), start=1):
            usage = [
                {
                    "tag": tag_name,
                    "property": property_name,
                    "count": len(node_ids),
                }
                for (tag_name, property_name), node_ids in sorted(
                    (entry.get("usage") or {}).items(),
                    key=lambda item: (item[0][0], item[0][1]),
                )
            ]
            payloads.append(
                {
                    "color_id": f"color-{index}",
                    "value": value,
                    "usage_count": len(entry.get("node_ids") or ()),
                    "node_ids": sorted(str(item) for item in (entry.get("node_ids") or ())),
                    "usage": usage,
                }
            )
        return cls.build(payloads)

    def __iter__(self) -> Iterator[ColorInventoryEntry]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def entry_by_id(self, color_id: str) -> ColorInventoryEntry | None:
        return next((entry for entry in self.entries if entry.color_id == color_id), None)

    def entry_by_value(self, value: str) -> ColorInventoryEntry | None:
        try:
            hex_value = color_registry.format_color(value, "hex")
            alpha = color_registry.alpha_of(value)
        except Exception:
            return None
        return next(
            (
                entry
                for entry in self.entries
                if entry.hex_value == hex_value and round(entry.alpha, 4) == round(alpha, 4)
            ),
            None,
        )

    def with_entries(self, entries: Iterable[ColorInventoryEntry | Mapping[str, Any]]) -> Self:
        return type(self).build(entries)

    def to_palette_dicts(self) -> list[dict[str, Any]]:
        return [entry.to_palette_entry() for entry in self.entries]

    def to_dict(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]


def _family_type_for_hct(hct_chroma: float) -> ColorFamilyType:
    return (
        ColorFamilyType.ACHROMATIC
        if hct_chroma < _ACHROMATIC_CHROMA_THRESHOLD
        else ColorFamilyType.CHROMATIC
    )


def _color_id_sort_key(color_id: str) -> tuple[int, int | str]:
    match = _COLOR_ID_RE.match(str(color_id or "").strip())
    if match:
        return (0, int(match.group(1)))
    return (1, str(color_id or ""))


def _build_property_usage_models(
    usages_by_property: Mapping[str, Mapping[str, int]],
) -> tuple[PropertyUsageModel, ...]:
    models: list[PropertyUsageModel] = []
    for property_name, tag_counts in sorted(usages_by_property.items()):
        tag_models = tuple(
            TagUsageModel(tag=tag_name, count=count)
            for tag_name, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
        )
        models.append(
            PropertyUsageModel(
                property_name=property_name,
                total_count=sum(item.count for item in tag_models),
                tags=tag_models,
            )
        )
    return tuple(models)


def _coerce_color_payload(payload: Mapping[str, Any] | ColorInventoryEntry) -> Mapping[str, Any]:
    if isinstance(payload, ColorInventoryEntry):
        return payload.to_dict()
    return payload


@dataclass(frozen=True, slots=True)
class SnapshotColorEvidence:
    color_id: str
    rgb: tuple[int, int, int]
    alpha: float
    hct: tuple[float, float, float]
    family_type: ColorFamilyType
    usage_count: int
    foreground_count: int
    background_count: int
    other_count: int
    foreground_color_usages: tuple[PropertyUsageModel, ...] = field(default_factory=tuple)
    background_color_usages: tuple[PropertyUsageModel, ...] = field(default_factory=tuple)
    other_usages: tuple[PropertyUsageModel, ...] = field(default_factory=tuple)
    confirmed_pixel_count: int = 0
    nearest_web_color: str | None = None
    nearest_web_color_distance: float | None = None
    confirmation_status: ColorConfirmationStatus = ColorConfirmationStatus.SEMANTIC_ONLY
    mapped_palette_id: str | None = None
    mapped_tone: int | None = None
    mapped_tone_rgb: tuple[int, int, int] | None = None
    mapped_tone_distance: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "family_type",
            _coerce_color_family_type(self.family_type),
        )
        object.__setattr__(
            self,
            "confirmation_status",
            _coerce_confirmation_status(self.confirmation_status),
        )

    @classmethod
    def build(cls, payload: Mapping[str, Any] | ColorInventoryEntry) -> Self | None:
        color_payload = _coerce_color_payload(payload)
        value = str(color_payload.get("value") or "").strip()
        if not value:
            return None

        hct = color_registry.hct_of(value)
        rgb = color_registry.format_color(value, "rgb")
        match = nearest_web_color(rgb)

        foreground_count = 0
        background_count = 0
        other_count = 0
        confirmed_pixel_count = int(
            color_payload.get("display_pixel_count")
            or color_payload.get("confirmed_pixel_count")
            or 0
        )
        foreground_usages: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        background_usages: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        other_usages: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for usage in color_payload.get("usage", ()) or ():
            if not isinstance(usage, Mapping):
                continue
            property_name = str(usage.get("property") or "")
            tag_name = str(usage.get("tag") or "")
            count = int(usage.get("count") or 0)
            property_spec = get_css_property(property_name)
            if property_spec and property_spec.color_role == CssColorRole.BACKGROUND:
                background_count += count
                background_usages[property_name][tag_name] += count
            elif property_spec and property_spec.color_role == CssColorRole.FOREGROUND:
                foreground_count += count
                foreground_usages[property_name][tag_name] += count
            else:
                other_count += count
                other_usages[property_name][tag_name] += count

        for observed_role in color_payload.get("observed_roles", ()) or ():
            if not isinstance(observed_role, Mapping):
                continue
            role_name = str(observed_role.get("role") or "").strip().lower()
            count = int(observed_role.get("count") or 0)
            if role_name == "background":
                background_count += count
            elif role_name == "text":
                foreground_count += count
            elif role_name:
                other_count += count

        return cls(
            color_id=str(color_payload.get("color_id") or ""),
            rgb=rgb,
            alpha=color_registry.alpha_of(value),
            hct=hct,  # type: ignore[arg-type]
            family_type=_family_type_for_hct(hct[1]),
            usage_count=int(color_payload.get("usage_count") or 0),
            foreground_count=foreground_count,
            background_count=background_count,
            other_count=other_count,
            foreground_color_usages=_build_property_usage_models(foreground_usages),
            background_color_usages=_build_property_usage_models(background_usages),
            other_usages=_build_property_usage_models(other_usages),
            confirmed_pixel_count=confirmed_pixel_count,
            nearest_web_color=match.color_name,
            nearest_web_color_distance=round(match.distance, 4),
            confirmation_status=(
                ColorConfirmationStatus.CONFIRMED
                if confirmed_pixel_count > 0
                else ColorConfirmationStatus.SEMANTIC_ONLY
            ),
        )

    @classmethod
    def build_many(cls, payloads: Any) -> tuple[Self, ...]:
        if not payloads:
            return ()
        return tuple(
            evidence
            for evidence in (
                cls.build(item)
                for item in payloads
                if isinstance(item, (ColorInventoryEntry, Mapping))
            )
            if evidence is not None
        )

    @classmethod
    def confirm_many(
        cls,
        evidences: tuple[Self, ...],
        pixel_records: tuple[PixelColorRecord, ...],
        *,
        delta_e_threshold: float = _PIXEL_CONFIRMATION_DELTA_E_THRESHOLD,
    ) -> tuple[tuple[Self, ...], int, int]:
        if not evidences:
            residual_pixels = sum(item.count for item in pixel_records)
            return (), 0, residual_pixels

        evidence_colors = {
            evidence.color_id: color_registry.parse_color(evidence.rgb)
            for evidence in evidences
        }
        confirmed_counts = {evidence.color_id: 0 for evidence in evidences}
        residual_pixel_count = 0
        residual_distinct_colors = 0

        for pixel_record in pixel_records:
            pixel_color = color_registry.parse_color(pixel_record.color)
            best_match = min(
                evidences,
                key=lambda evidence: color_registry.delta_e_distance(
                    pixel_color,
                    evidence_colors[evidence.color_id],
                    method="2000",
                ),
            )
            distance = color_registry.delta_e_distance(
                pixel_color,
                evidence_colors[best_match.color_id],
                method="2000",
            )
            if distance <= delta_e_threshold:
                confirmed_counts[best_match.color_id] += pixel_record.count
            else:
                residual_pixel_count += pixel_record.count
                residual_distinct_colors += 1

        confirmed_evidences = tuple(
            evidence.with_confirmed_pixels(confirmed_counts[evidence.color_id])
            for evidence in evidences
        )
        return confirmed_evidences, residual_distinct_colors, residual_pixel_count

    def with_confirmed_pixels(self, confirmed_pixel_count: int) -> Self:
        return replace(
            self,
            confirmed_pixel_count=confirmed_pixel_count,
            confirmation_status=(
                ColorConfirmationStatus.CONFIRMED
                if confirmed_pixel_count > 0
                else ColorConfirmationStatus.SEMANTIC_ONLY
            ),
        )

    def with_palette_mapping(
        self,
        *,
        palette_id: str,
        tone: int,
        tone_rgb: tuple[int, int, int],
        tone_distance: float,
    ) -> Self:
        return replace(
            self,
            mapped_palette_id=palette_id,
            mapped_tone=tone,
            mapped_tone_rgb=tone_rgb,
            mapped_tone_distance=round(tone_distance, 4),
        )

    def __iter__(self) -> Iterator[PropertyUsageModel]:
        yield from self.foreground_color_usages
        yield from self.background_color_usages
        yield from self.other_usages

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rgb"] = list(self.rgb)
        payload["hct"] = list(self.hct)
        payload["family_type"] = self.family_type.value
        payload["confirmation_status"] = self.confirmation_status.value
        payload["foreground_color_usages"] = [
            item.to_dict() for item in self.foreground_color_usages
        ]
        payload["background_color_usages"] = [
            item.to_dict() for item in self.background_color_usages
        ]
        payload["other_usages"] = [item.to_dict() for item in self.other_usages]
        if self.mapped_tone_rgb is not None:
            payload["mapped_tone_rgb"] = list(self.mapped_tone_rgb)
        return payload


def build_inventory_from_scheme_colors(
    evidences: Iterable[SnapshotColorEvidence | Mapping[str, Any]],
) -> ColorInventoryModel:
    payloads: list[dict[str, Any]] = []
    for raw_evidence in evidences:
        evidence = (
            raw_evidence
            if isinstance(raw_evidence, SnapshotColorEvidence)
            else SnapshotColorEvidence.build(raw_evidence)
        )
        if evidence is None:
            continue

        usage_rows: list[dict[str, Any]] = []
        for property_usage in evidence:
            for tag_usage in property_usage.tags:
                usage_rows.append(
                    {
                        "tag": tag_usage.tag,
                        "property": property_usage.property_name,
                        "count": tag_usage.count,
                    }
                )

        payloads.append(
            {
                "color_id": evidence.color_id,
                "value": color_registry.format_color((*evidence.rgb, evidence.alpha), "css"),
                "usage_count": evidence.usage_count,
                "usage": usage_rows,
                "display_pixel_count": evidence.confirmed_pixel_count,
                "mapped_palette_id": evidence.mapped_palette_id,
                "mapped_tone": evidence.mapped_tone,
                "mapped_tone_rgb": list(evidence.mapped_tone_rgb)
                if evidence.mapped_tone_rgb is not None
                else None,
                "mapped_tone_distance": evidence.mapped_tone_distance,
            }
        )

    return ColorInventoryModel.build(payloads)


ColorModel = ColorInventoryEntry
