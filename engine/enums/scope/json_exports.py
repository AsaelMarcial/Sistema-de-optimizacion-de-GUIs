from __future__ import annotations

import json
from pathlib import Path

from engine.enums.scope.css_properties import get_in_scope_css_properties
from engine.enums.scope.html_elements import HTML_ELEMENT_SPECS, HtmlElementScopeGroup


DICTIONARIES_DIR = (
    Path(__file__).resolve().parents[2] / "models" / "legacy" / "dictionaries"
)


def build_scope_properties_payload() -> dict:
    return {
        "onScope": [
            {
                "propertyID": spec.property_id.value,
                "categories": [category.value for category in spec.categories],
                "computedAliases": list(spec.computed_aliases),
                "shorthandFor": [item.value for item in spec.shorthand_for],
                "longhandOf": spec.longhand_of.value if spec.longhand_of else None,
                "colorRole": spec.color_role.value if spec.color_role else None,
                "affectsVisibility": spec.affects_visibility,
                "affectsPaintOrder": spec.affects_paint_order,
            }
            for spec in get_in_scope_css_properties()
        ]
    }


def build_scope_elements_payload() -> dict:
    return {
        "onScope": [
            {
                "elementID": spec.element_id.value,
                "name": spec.element_id.value,
                "description": spec.description,
                "scopeGroup": spec.scope_group.value,
                "categories": list(spec.categories),
                "isVisible": spec.is_visible,
                "captureText": spec.capture_text,
                "captureChildren": spec.capture_children,
            }
            for spec in HTML_ELEMENT_SPECS
            if spec.scope_group != HtmlElementScopeGroup.IGNORED
        ]
    }


def sync_scope_json_files() -> None:
    DICTIONARIES_DIR.mkdir(parents=True, exist_ok=True)
    (DICTIONARIES_DIR / "scope-properties.json").write_text(
        json.dumps(build_scope_properties_payload(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (DICTIONARIES_DIR / "scope-elements.json").write_text(
        json.dumps(build_scope_elements_payload(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    # Manual export utility for legacy JSON snapshots only.
    sync_scope_json_files()
