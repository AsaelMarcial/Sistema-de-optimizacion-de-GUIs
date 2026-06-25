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
DEFAULT_VALUE = "defaultValue"
SHORTHAND = "shorthand"


# =============================================================================
# INTERNAL
# =============================================================================


def _propertyData(
    *,
    category: Category,
    supportsColor: bool,
    role: Role,
    defaultValue: str | tuple[str, ...] = (),
    shorthand: str = "",
) -> MappingProxyType:
    default_values = (defaultValue,) if isinstance(
        defaultValue, str) else tuple(defaultValue)
    return MappingProxyType(
        {
            CATEGORY: category,
            SUPPORTS_COLOR: supportsColor,
            ROLE: role,
            DEFAULT_VALUE: default_values,
            SHORTHAND: shorthand,
        }
    )


# =============================================================================
# CSS PROPERTIES
# =============================================================================


CSS_PROPERTIES = MappingProxyType(
    {
        "accent-color": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue="auto",
        ),
        "background": _propertyData(
            category=Category.BACKGROUND,
            supportsColor=True,
            role=Role.BACKGROUND,
            defaultValue=("none"),
        ),
        "background-color": _propertyData(
            category=Category.BACKGROUND,
            supportsColor=True,
            role=Role.BACKGROUND,
            defaultValue=(),
            shorthand="background",
        ),
        "background-image": _propertyData(
            category=Category.BACKGROUND,
            supportsColor=True,
            role=Role.BACKGROUND,
            defaultValue="none",
            shorthand="background",
        ),
        "border": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=("0px", "none"),
        ),
        "border-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border",
        ),
        "border-bottom-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border-color",
        ),
        "border-left-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border-color",
        ),
        "border-right-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border-color",
        ),
        "border-top-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border-color",
        ),
        "border-block": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=("0px", "none"),
        ),
        "border-block-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border-block",
        ),
        "border-block-end-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border-block-color",
        ),
        "border-block-start-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border-block-color",
        ),
        "border-image": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue="none",
        ),
        "border-image-source": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue="none",
            shorthand="border-image",
        ),
        "border-inline": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=("0px", "none"),
        ),
        "border-inline-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border-inline",
        ),
        "border-inline-end-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border-inline-color",
        ),
        "border-inline-start-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="border-inline-color",
        ),
        "box-shadow": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue="none",
        ),
        "color": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
        ),
        "column-rule": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=("0px", "none"),
        ),
        "column-rule-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="column-rule",
        ),
        "fill": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
        ),
        "flood-color": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
        ),
        "lighting-color": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
        ),
        "list-style-image": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue="none",
        ),
        "outline": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=("0px", "none"),
        ),
        "outline-color": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="outline",
        ),
        "stop-color": _propertyData(
            category=Category.DECORATION,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
        ),
        "stroke": _propertyData(
            category=Category.BORDER,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue="none",
        ),
        "text-decoration": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue="none",
        ),
        "text-decoration-color": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="text-decoration",
        ),
        "text-emphasis": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue="none",
        ),
        "text-emphasis-color": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue=(),
            shorthand="text-emphasis",
        ),
        "text-shadow": _propertyData(
            category=Category.TYPOGRAPHY,
            supportsColor=True,
            role=Role.FOREGROUND,
            defaultValue="none",
        ),
    }
)


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
