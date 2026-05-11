from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
import re
from typing import Any, Iterable, Iterator, Mapping, Self

from engine.domain.data.web_colors import nearest_web_color
from engine.adapters.color_service import color_registry
from engine.domain.enums.scope.css_properties import CssColorRole, CssPropertyId, get_css_property
from engine.domain.enums.types.color import (
    ColorConfirmationStatus,
    ColorFamilyType,
    ObservedColorRole,
)

_ACHROMATIC_CHROMA_THRESHOLD = 8.0
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


def _coerce_css_property_id(
    value: CssPropertyId | str | None,
) -> CssPropertyId:
    if isinstance(value, CssPropertyId):
        return value
    property_id = get_css_property(value)
    if property_id is None:
        raise ValueError(f"Propiedad CSS fuera de scope o invalida: {value!r}")
    return property_id


def _coerce_observed_color_role(
    value: ObservedColorRole | str | None,
) -> ObservedColorRole:
    if isinstance(value, ObservedColorRole):
        return value
    normalized = str(value or ObservedColorRole.OTHER.value).strip().lower()
    return ObservedColorRole(normalized or ObservedColorRole.OTHER.value)


@dataclass(frozen=True, slots=True)
class TagUsage:
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
class PropertyUsage:
    property_name: CssPropertyId
    total_count: int
    tags: tuple[TagUsage, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            property_name=_coerce_css_property_id(
                payload.get("property") or payload.get("property_name")
            ),
            total_count=int(payload.get("total_count") or 0),
            tags=tuple(
                TagUsage.build(item)
                for item in (payload.get("tags") or ())
                if isinstance(item, Mapping)
            ),
        )

    def __iter__(self) -> Iterator[TagUsage]:
        return iter(self.tags)

    def to_dict(self) -> dict[str, Any]:
        return {
            "property": self.property_name.value,
            "total_count": self.total_count,
            "tags": [item.to_dict() for item in self.tags],
        }


@dataclass(frozen=True, slots=True)
class ColorUsage:
    tag: str
    property_name: CssPropertyId
    count: int

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            tag=str(payload.get("tag") or ""),
            property_name=_coerce_css_property_id(
                payload.get("property") or payload.get("property_name")
            ),
            count=int(payload.get("count") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "property": self.property_name.value,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class ObservedRole:
    role: ObservedColorRole
    count: int
    node_ids: tuple[str, ...] = field(default_factory=tuple)
    sample_selectors: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            role=_coerce_observed_color_role(payload.get("role")),
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
            "role": self.role.value,
            "count": self.count,
        }
        if self.node_ids:
            payload["node_ids"] = list(self.node_ids)
        if self.sample_selectors:
            payload["sample_selectors"] = list(self.sample_selectors)
        return payload


@dataclass(frozen=True, slots=True)
class Color:
    color_id: str
    value: str
    hex_value: str
    rgb: tuple[int, int, int]
    alpha: float
    hct: tuple[float, float, float]
    family_type: ColorFamilyType
    usage_count: int
    foreground_count: int = 0
    background_count: int = 0
    other_count: int = 0
    node_ids: tuple[str, ...] = field(default_factory=tuple)
    usage: tuple[ColorUsage, ...] = field(default_factory=tuple)
    foreground_color_usages: tuple[PropertyUsage, ...] = field(default_factory=tuple)
    background_color_usages: tuple[PropertyUsage, ...] = field(default_factory=tuple)
    other_usages: tuple[PropertyUsage, ...] = field(default_factory=tuple)
    observed_usage_count: int = 0
    observed_roles: tuple[ObservedRole, ...] = field(default_factory=tuple)
    nearest_web_color: str | None = None
    nearest_web_color_distance: float | None = None
    confirmation_status: ColorConfirmationStatus = ColorConfirmationStatus.SEMANTIC_ONLY
    declared_in_snapshot: bool = True
    pixel_count: int = 0
    pixel_percentage: float | None = None
    mapped_palette_id: str | None = None
    mapped_tone: int | None = None
    mapped_tone_rgb: tuple[int, int, int] | None = None
    mapped_tone_distance: float | None = None
    token_ids: tuple[str, ...] = field(default_factory=tuple)
    foundation_token_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "family_type", _coerce_color_family_type(self.family_type))
        object.__setattr__(
            self,
            "confirmation_status",
            _coerce_confirmation_status(self.confirmation_status),
        )

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        value = str(payload.get("value") or "").strip()
        rgb = color_registry.format_color(value, "rgb")
        hct = color_registry.hct_of(value)
        nearest_match = nearest_web_color(rgb)
        node_ids = tuple(
            str(item).strip()
            for item in (payload.get("node_ids") or ())
            if str(item).strip()
        )
        observed_roles = tuple(
            ObservedRole.build(item)
            for item in (payload.get("observed_roles") or ())
            if isinstance(item, Mapping)
        )
        observed_node_ids = {
            node_id
            for role in observed_roles
            for node_id in role.node_ids
        }
        foreground_count = int(payload.get("foreground_count") or 0)
        background_count = int(payload.get("background_count") or 0)
        other_count = int(payload.get("other_count") or 0)
        foreground_usages: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        background_usages: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        other_usages: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for usage in payload.get("usage", ()) or ():
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
        for observed_role in observed_roles:
            if observed_role.role == ObservedColorRole.BACKGROUND:
                background_count += observed_role.count
            elif observed_role.role == ObservedColorRole.TEXT:
                foreground_count += observed_role.count
            elif observed_role.role != ObservedColorRole.OTHER:
                other_count += observed_role.count
        pixel_count = int(payload.get("pixel_count") or 0)
        return cls(
            color_id=str(payload.get("color_id") or ""),
            value=value,
            hex_value=color_registry.format_color(value, "hex"),
            rgb=rgb,
            alpha=color_registry.alpha_of(value),
            hct=hct,
            family_type=_family_type_for_hct(hct[1]),
            usage_count=int(payload.get("usage_count") or len(node_ids) or 0),
            foreground_count=foreground_count,
            background_count=background_count,
            other_count=other_count,
            node_ids=node_ids,
            usage=tuple(
                ColorUsage.build(item)
                for item in (payload.get("usage") or ())
                if isinstance(item, Mapping)
            ),
            foreground_color_usages=(
                tuple(
                    item if isinstance(item, PropertyUsage) else PropertyUsage.build(item)
                    for item in (payload.get("foreground_color_usages") or ())
                    if isinstance(item, (PropertyUsage, Mapping))
                )
                or _build_property_usage_models(foreground_usages)
            ),
            background_color_usages=(
                tuple(
                    item if isinstance(item, PropertyUsage) else PropertyUsage.build(item)
                    for item in (payload.get("background_color_usages") or ())
                    if isinstance(item, (PropertyUsage, Mapping))
                )
                or _build_property_usage_models(background_usages)
            ),
            other_usages=(
                tuple(
                    item if isinstance(item, PropertyUsage) else PropertyUsage.build(item)
                    for item in (payload.get("other_usages") or ())
                    if isinstance(item, (PropertyUsage, Mapping))
                )
                or _build_property_usage_models(other_usages)
            ),
            observed_usage_count=(
                int(payload.get("observed_usage_count") or len(observed_node_ids) or 0)
            ),
            observed_roles=observed_roles,
            nearest_web_color=nearest_match.color_name,
            nearest_web_color_distance=round(nearest_match.distance, 4),
            confirmation_status=(
                payload.get("confirmation_status")
                or (
                    ColorConfirmationStatus.CONFIRMED
                    if pixel_count > 0
                    else ColorConfirmationStatus.SEMANTIC_ONLY
                )
            ),
            declared_in_snapshot=bool(payload.get("declared_in_snapshot", True)),
            pixel_count=pixel_count,
            pixel_percentage=(
                round(float(payload["pixel_percentage"]), 4)
                if payload.get("pixel_percentage") is not None
                else None
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
            token_ids=tuple(
                dict.fromkeys(
                    str(item).strip()
                    for item in (payload.get("token_ids") or ())
                    if str(item).strip()
                )
            ),
            foundation_token_id=(
                str(payload["foundation_token_id"])
                if payload.get("foundation_token_id") is not None
                else None
            ),
        )

    @classmethod
    def build_many(cls, payloads: Iterable["Color" | Mapping[str, Any]] | None) -> tuple[Self, ...]:
        return ColorCatalog.build(payloads).entries

    def signature(self) -> tuple[str, float]:
        return self.hex_value, round(self.alpha, 4)

    def merge(self, other: Self) -> Self:
        merged_usage: dict[tuple[str, str], int] = defaultdict(int)
        for usage_item in (*self.usage, *other.usage):
            merged_usage[(usage_item.tag, usage_item.property_name)] += usage_item.count
        merged_usage_models = tuple(
            ColorUsage(tag=tag, property_name=property_name, count=count)
            for (tag, property_name), count in sorted(merged_usage.items())
        )
        merged_node_ids = tuple(sorted({*self.node_ids, *other.node_ids}))
        merged_roles: dict[ObservedColorRole, ObservedRole] = {}
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
            foreground_count=self.foreground_count + other.foreground_count,
            background_count=self.background_count + other.background_count,
            other_count=self.other_count + other.other_count,
            node_ids=merged_node_ids,
            usage=merged_usage_models,
            observed_usage_count=(
                len(observed_node_ids)
                if observed_node_ids
                else self.observed_usage_count + other.observed_usage_count
            ),
            observed_roles=merged_observed_roles,
            declared_in_snapshot=self.declared_in_snapshot or other.declared_in_snapshot,
            pixel_count=self.pixel_count + other.pixel_count,
            pixel_percentage=(
                round(
                    (self.pixel_percentage or 0.0)
                    + (other.pixel_percentage or 0.0),
                    4,
                )
                if self.pixel_percentage is not None
                or other.pixel_percentage is not None
                else None
            ),
            token_ids=tuple(dict.fromkeys((*self.token_ids, *other.token_ids)).keys()),
            foundation_token_id=self.foundation_token_id or other.foundation_token_id,
        )

    def property_names(self) -> tuple[CssPropertyId, ...]:
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

    def set_count(
        self,
        count: int,
        percentage: float | None = None,
    ) -> Self:
        visible_pixels = int(count)
        return replace(
            self,
            pixel_count=visible_pixels,
            confirmation_status=(
                ColorConfirmationStatus.CONFIRMED
                if visible_pixels > 0
                else ColorConfirmationStatus.SEMANTIC_ONLY
            ),
            pixel_percentage=(
                round(float(percentage), 4)
                if percentage is not None
                else self.pixel_percentage
            ),
        )

    def with_token_assignment(
        self,
        token_id: str,
        *,
        foundation: bool = False,
    ) -> Self:
        normalized_token_id = str(token_id or "").strip()
        if not normalized_token_id:
            return self
        return replace(
            self,
            token_ids=tuple(dict.fromkeys((*self.token_ids, normalized_token_id)).keys()),
            foundation_token_id=normalized_token_id if foundation else self.foundation_token_id,
        )

    def __iter__(self) -> Iterator[PropertyUsage]:
        yield from self.foreground_color_usages
        yield from self.background_color_usages
        yield from self.other_usages

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
        payload["family_type"] = self.family_type.value
        payload["foreground_count"] = self.foreground_count
        payload["background_count"] = self.background_count
        payload["other_count"] = self.other_count
        payload["foreground_color_usages"] = [
            item.to_dict() for item in self.foreground_color_usages
        ]
        payload["background_color_usages"] = [
            item.to_dict() for item in self.background_color_usages
        ]
        payload["other_usages"] = [item.to_dict() for item in self.other_usages]
        payload["confirmation_status"] = self.confirmation_status.value
        if self.nearest_web_color is not None:
            payload["nearest_web_color"] = self.nearest_web_color
        if self.nearest_web_color_distance is not None:
            payload["nearest_web_color_distance"] = self.nearest_web_color_distance
        if not self.declared_in_snapshot:
            payload["declared_in_snapshot"] = False
        if self.observed_usage_count:
            payload["observed_usage_count"] = self.observed_usage_count
        if self.observed_roles:
            payload["observed_roles"] = [item.to_dict() for item in self.observed_roles]
        if self.pixel_count:
            payload["pixel_count"] = self.pixel_count
        if self.pixel_percentage is not None and self.pixel_percentage > 0:
            payload["pixel_percentage"] = self.pixel_percentage
        if self.mapped_palette_id is not None:
            payload["mapped_palette_id"] = self.mapped_palette_id
        if self.mapped_tone is not None:
            payload["mapped_tone"] = self.mapped_tone
        if self.mapped_tone_rgb is not None:
            payload["mapped_tone_rgb"] = list(self.mapped_tone_rgb)
        if self.mapped_tone_distance is not None:
            payload["mapped_tone_distance"] = self.mapped_tone_distance
        if self.token_ids:
            payload["token_ids"] = list(self.token_ids)
        if self.foundation_token_id is not None:
            payload["foundation_token_id"] = self.foundation_token_id
        return payload


@dataclass(frozen=True, slots=True)
class ColorCatalog:
    entries: tuple[Color, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payloads: Iterable[Color | Mapping[str, Any]] | None) -> Self:
        if not payloads:
            return cls()

        normalized_payloads = tuple(payloads)
        deduped: dict[tuple[str, float], Color] = {}
        generated_index = max(
            (
                int(color_id.split("-")[-1])
                for color_id in (
                    (
                        str(payload.color_id)
                        if isinstance(payload, Color)
                        else str(payload.get("color_id") or "")
                    )
                    for payload in normalized_payloads
                )
                if color_id.startswith("color-") and color_id.split("-")[-1].isdigit()
            ),
            default=0,
        )
        for payload in normalized_payloads:
            entry = payload if isinstance(payload, Color) else Color.build(payload)
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
                    "property": property_name.value
                    if isinstance(property_name, CssPropertyId)
                    else str(property_name),
                    "count": len(node_ids),
                }
                for (tag_name, property_name), node_ids in sorted(
                    (entry.get("usage") or {}).items(),
                    key=lambda item: (
                        item[0][0],
                        item[0][1].value if isinstance(item[0][1], CssPropertyId) else str(item[0][1]),
                    ),
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

    def __iter__(self) -> Iterator[Color]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def entry_by_id(self, color_id: str) -> Color | None:
        return next((entry for entry in self.entries if entry.color_id == color_id), None)

    def entry_by_value(self, value: str) -> Color | None:
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

    def with_entries(self, entries: Iterable[Color | Mapping[str, Any]]) -> Self:
        return type(self).build(entries)

    def with_pixel_counts(
        self,
        counts_by_color_id: Mapping[str, tuple[int, float]],
    ) -> Self:
        return self.with_entries(
            entry.set_count(
                int(counts_by_color_id[entry.color_id][0]),
                percentage=float(counts_by_color_id[entry.color_id][1]),
            )
            if entry.color_id in counts_by_color_id
            else entry
            for entry in self.entries
        )

    def with_palette_mappings(
        self,
        mapped_entries: Iterable[Color],
    ) -> Self:
        mapped_by_id = {
            entry.color_id: entry
            for entry in mapped_entries
            if entry.color_id
        }
        return self.with_entries(
            entry.with_palette_mapping(
                palette_id=mapped_entry.mapped_palette_id,
                tone=mapped_entry.mapped_tone,
                tone_rgb=mapped_entry.mapped_tone_rgb,
                tone_distance=mapped_entry.mapped_tone_distance,
            )
            if (
                (mapped_entry := mapped_by_id.get(entry.color_id)) is not None
                and mapped_entry.mapped_palette_id is not None
                and mapped_entry.mapped_tone is not None
                and mapped_entry.mapped_tone_rgb is not None
                and mapped_entry.mapped_tone_distance is not None
            )
            else entry
            for entry in self.entries
        )

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
    usages_by_property: Mapping[CssPropertyId | str, Mapping[str, int]],
) -> tuple[PropertyUsage, ...]:
    models: list[PropertyUsage] = []
    normalized_usages = {
        _coerce_css_property_id(property_name): tag_counts
        for property_name, tag_counts in usages_by_property.items()
    }
    for property_name, tag_counts in sorted(normalized_usages.items(), key=lambda item: item[0].value):
        tag_models = tuple(
            TagUsage(tag=tag_name, count=count)
            for tag_name, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
        )
        models.append(
            PropertyUsage(
                property_name=property_name,
                total_count=sum(item.count for item in tag_models),
                tags=tag_models,
            )
        )
    return tuple(models)

