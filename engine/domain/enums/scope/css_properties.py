from enum import StrEnum
from types import MappingProxyType


# =============================================================================
# CATEGORY
# =============================================================================


class Category(StrEnum):
    BACKGROUND = "background"
    BORDER = "border"
    DECORATION = "decoration"
    TYPOGRAPHY = "typography"
    OTHER = "other"


# =============================================================================
# ROLE
# =============================================================================


class Role(StrEnum):
    BACKGROUND = "background"
    FOREGROUND = "foreground"
    OTHER = "other"


# =============================================================================
# KEYS
# =============================================================================


CATEGORY = "category"
SUPPORTS_COLOR = "supportsColor"
ROLE = "role"


# =============================================================================
# INTERNAL
# =============================================================================


def _propertyData(
    *,
    category: Category,
    supportsColor: bool,
    role: Role,
) -> MappingProxyType:
    return MappingProxyType(
        {
            CATEGORY: category,
            SUPPORTS_COLOR: supportsColor,
            ROLE: role,
        }
    )


# =============================================================================
# CSS PROPERTIES
# =============================================================================


CSS_PROPERTIES = MappingProxyType(
    {
        # =====================================================================
        # BACKGROUND
        # =====================================================================
        "background": _propertyData(
            category=Category.BACKGROUND,
            supportsColor=True,
            role=Role.BACKGROUND,
        ),
        "background-color": _propertyData(
            category=Category.BACKGROUND,
            supportsColor=True,
            role=Role.BACKGROUND,
        ),
        "background-image": _propertyData(
            category=Category.BACKGROUND,
            supportsColor=True,
            role=Role.BACKGROUND,
        ),
        # =====================================================================
        # BORDER
        # =====================================================================
        "border": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-top-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-right-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-bottom-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-left-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-block-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-inline-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-block-start-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-block-end-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-inline-start-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-inline-end-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "outline": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "outline-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "column-rule": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "column-rule-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        # =====================================================================
        # DECORATION
        # =====================================================================
        "box-shadow": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "text-shadow": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "filter": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "backdrop-filter": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "mask": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "mask-image": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "mask-border": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "mask-border-source": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-image": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "border-image-source": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "text-decoration": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "text-decoration-color": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "text-emphasis": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "text-emphasis-color": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "accent-color": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "fill": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "stroke": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "stop-color": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "flood-color": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "lighting-color": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        # =====================================================================
        # TYPOGRAPHY
        # =====================================================================
        "color": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "caret": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "caret-color": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "-webkit-text-fill-color": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "-webkit-text-stroke": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "-webkit-text-stroke-color": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "text-fill-color": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        "text-stroke-color": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
        ),
        # =====================================================================
        # OTHER
        # =====================================================================
        "appearance": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "background-attachment": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "background-blend-mode": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "background-clip": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "background-origin": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "background-position": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "background-repeat": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "background-size": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "border-radius": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "display": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "fill-opacity": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "fill-rule": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "font-family": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "font-size": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "font-style": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "font-weight": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "height": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "letter-spacing": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "line-height": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "object-fit": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "object-position": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "opacity": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "outline-offset": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "position": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "stroke-opacity": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "text-decoration-line": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "text-decoration-style": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "text-decoration-thickness": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "text-rendering": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "visibility": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "width": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "word-spacing": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
        "z-index": _propertyData(
            category=Category.OTHER,
            supportsColor=False,
            role=Role.OTHER,
        ),
    }
)


# =============================================================================
# PRECOMPUTED INDEXES
# =============================================================================


ALL_PROPERTY_NAMES = tuple(CSS_PROPERTIES.keys())


COLOR_SUPPORTED_PROPERTIES = tuple(
    property_name
    for property_name, property_data in CSS_PROPERTIES.items()
    if property_data[SUPPORTS_COLOR]
)


PROPERTIES_BY_CATEGORY = MappingProxyType(
    {
        category: tuple(
            property_name
            for property_name, property_data in CSS_PROPERTIES.items()
            if property_data[CATEGORY] == category
        )
        for category in Category
    }
)


PROPERTIES_BY_ROLE = MappingProxyType(
    {
        role: tuple(
            property_name
            for property_name, property_data in CSS_PROPERTIES.items()
            if property_data[ROLE] == role
        )
        for role in Role
    }
)


# =============================================================================
# HELPERS
# =============================================================================


def getAllPropertyNames() -> tuple[str, ...]:
    return ALL_PROPERTY_NAMES


def getPropertiesByCategory(category: Category) -> tuple[str, ...]:
    return PROPERTIES_BY_CATEGORY[category]


def getPropertiesByRole(role: Role) -> tuple[str, ...]:
    return PROPERTIES_BY_ROLE[role]


def getColorSupportedProperties() -> tuple[str, ...]:
    return COLOR_SUPPORTED_PROPERTIES
