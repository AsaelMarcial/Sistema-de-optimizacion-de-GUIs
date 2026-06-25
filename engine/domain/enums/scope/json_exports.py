import json
from pathlib import Path

from engine.domain.enums.scope.css_properties import (
    CATEGORY,
    DEFAULT_VALUE,
    ROLE,
    SHORTHAND,
    SUPPORTS_COLOR,
    CSS_PROPERTIES,
)
from engine.domain.enums.scope.html_elements import HTML_ELEMENT_SPECS, HtmlElementScopeGroup


DICTIONARIES_DIR = (
    Path(__file__).resolve().parents[3] / "models" / "legacy" / "dictionaries"
)


def build_scope_properties_payload() -> dict[str, list[dict[str, object]]]:
    return {
        "onScope": [
            {
                "propertyID": property_name,
                "category": property_data[CATEGORY].value,
                "supportsColor": bool(property_data[SUPPORTS_COLOR]),
                "role": property_data[ROLE].value,
                "defaultValue": list(property_data[DEFAULT_VALUE]),
                "shorthand": property_data[SHORTHAND],
            }
            for property_name, property_data in CSS_PROPERTIES.items()
        ]
    }


def build_scope_elements_payload() -> dict[str, list[dict[str, object]]]:
    return {
        "onScope": [
            {
                "elementID": spec.value,
                "name": spec.value,
                "description": spec.description,
                "scopeGroup": spec.scope_group.value,
                "categories": list(spec.categories),
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
    sync_scope_json_files()
