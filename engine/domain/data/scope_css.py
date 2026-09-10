from dataclasses import dataclass
from types import MappingProxyType
from typing import Tuple

# =====================================================================
# 1. ESTRUCTURA ULTRA-LIGERA
# =====================================================================
@dataclass(frozen=True)
class CSSDATA:
    __slots__ = ('role', 'categories', 'shorthand', 'longhands', 'default_value')
    role: str
    categories: Tuple[str, ...]
    shorthand: str | None
    longhands: Tuple[str, ...] | None
    default_value: Tuple[str, ...] | None

CSSPROPERTIES = MappingProxyType({
        "background": CSSDATA(
            role="background",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand=None,
            longhands=["background-color", "background-image"],
            default_value=None,
        ),
        "background-color": CSSDATA(
            role="background",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="background",
            longhands=None,
            default_value=[],
        ),
        "background-image": CSSDATA(
            role="background",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand= "background",
            longhands= None,
            default_value=["none"],
        ),        
        "fill": CSSDATA(
            role="background",
            categories=["decoration"],
            shorthand=None,
            longhands=None,
            default_value=None,
        ),
        "accent-color": CSSDATA(
            role="foreground",
            categories=["input"],
            shorthand=None,
            longhands=None,
            default_value=["auto"],
        ),
        "border": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand=None,
            longhands=["border-color"],
            default_value=["none", "0px"],
        ), 
        "border-left": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border",
            longhands=None,
            default_value=None,
        ),
        "border-right": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border",
            longhands=None,
            default_value=None,
        ),
        "border-top": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border",
            longhands=None,
            default_value=None,
        ),
        "border-bottom": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border",
            longhands=None,
            default_value=None,
        ),
        "border-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border",
            longhands=None,
            default_value=None,
        ),
        "border-left-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-color",
            longhands=None,
            default_value=None,
        ),
        "border-right-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-color",
            longhands=None,
            default_value=None,
        ),
        "border-top-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-color",
            longhands=None,
            default_value=None,
        ),
        "border-bottom-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-color",
            longhands=None,
            default_value=None,
        ),
        "border-block": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand=None,
            longhands=["border-block-color"],
            default_value=["none", "0px"],
        ),
        "border-block-start": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-block",
            longhands=None,
            default_value=None,
        ),
        "border-block-end": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-block",
            longhands=None,
            default_value=None,
        ),
        "border-block-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-block",
            longhands=["border-block-start-color","border-block-end-color"],
            default_value=None,
        ),
        "border-block-start-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-block-color",
            longhands=None,
            default_value=None,
        ),
        "border-block-end-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-block-color",
            longhands=None,
            default_value=None,
        ),
        "border-image": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand=None,
            longhands=["border-image-source"],
            default_value=["none"],
        ),
        "border-image-source": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-image",
            longhands=None,
            default_value=["none"],
        ),
        "border-inline": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand=None,
            longhands=["border-inline-color"],
            default_value=["none", "0px"],
        ),
        "border-inline-start": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-inline",
            longhands=None,
            default_value=None,
        ),
        "border-inline-end": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-inline",
            longhands=None,
            default_value=None,
        ),
        "border-inline-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-inline",
            longhands=["border-inline-start-color", "border-inline-end-color"],
            default_value=None,
        ),
        "border-inline-start-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-inline-color",
            longhands=None,
            default_value=None,
        ),
        "border-inline-end-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-inline-color",
            longhands=None,
            default_value=None,
        ),
        "box-shadow": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand=None,
            longhands=None,
            default_value=["none"],
        ),
        "column-rule": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "composed", "typography"],
            shorthand=None,
            longhands=["column-rule-color"],
            default_value=["0px"],
        ),
        "column-rule-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "composed", "typography"],
            shorthand="column-rule",
            longhands=None,
            default_value=None,
        ),

        "font-size": CSSDATA(
            role="other",
            categories=["typography"],
            shorthand=None,
            longhands=None,
            default_value=None,
        ),
        "font-weight": CSSDATA(
            role="other",
            categories=["typography"],
            shorthand=None,
            longhands=None,
            default_value=None,
        ),
        "list-style-image": CSSDATA(
            role="foreground",
            categories=["composed"],
            shorthand="list-style",
            longhands=None,
            default_value=["none"],
        ),
        "outline": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography"],
            shorthand=None,
            longhands=["outline-color"],
            default_value=["none", "0px"],
        ),
        "outline-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography"],
            shorthand="outline",
            longhands=None,
            default_value=None,
        ),
        "stroke": CSSDATA(
            role="foreground",
            categories=["decoration"],
            shorthand=None,
            longhands=None,
            default_value=["none"],
        ),
        "text-decoration": CSSDATA(
            role="foreground",
            categories=["typography"],
            shorthand=None,
            longhands=["text-decoration-color"],
            default_value=["none"],
        ),
        "text-decoration-color": CSSDATA(
            role="foreground",
            categories=["typography"],
            shorthand="text-decoration",
            longhands=None,
            default_value=None,
        ),
        "text-emphasis": CSSDATA(
            role="foreground",
            categories=["typography"],
            shorthand=None,
            longhands=["text-emphasis-color"],
            default_value=["none"],
        ),
        "text-emphasis-color": CSSDATA(
            role="foreground",
            categories=["typography"],
            shorthand="text-emphasis",
            longhands=None,
            default_value=None,
        ),
        "text-shadow": CSSDATA(
            role="foreground",
            categories=["typography"],
            shorthand=None,
            longhands=None,
            default_value=["none"],
        ),
        "color": CSSDATA(
            role="foreground",
            categories=["typography"],
            shorthand=None,
            longhands=None,
            default_value=None,
        ),
    }
)

def get_singular_properties() -> tuple[str, ...]:
    return [key for key in CSSPROPERTIES if (CSSPROPERTIES[key].longhands is None and CSSPROPERTIES[key].shorthand is None)] 

def getAllShorthandProperties() -> tuple[str, ...]:
    shorthand_names = []
    for key in CSSPROPERTIES:
        if CSSPROPERTIES[key].longhands is not None:
            shorthand_names.append(key)
    return tuple(shorthand_names)

def collect_longhands(property_name: str) -> set[str]:
    longhands: set[str] = set()
    for longhand in CSSPROPERTIES[property_name].longhands or ():
        longhands.add(longhand)
        longhands.update(collect_longhands(longhand))
    return longhands

def get_shorthand(property_name: str) -> str | None:
    property_data = CSSPROPERTIES.get(property_name)
    return property_data.shorthand if property_data is not None else None

def get_default_values(property_name: str) -> any:
    property_data = CSSPROPERTIES.get(property_name)
    return property_data.default_value if property_data is not None and property_data.default_value else None

def get_role(property_name: str) -> str | None:
    property_data = CSSPROPERTIES.get(property_name)
    return property_data.role if property_data is not None else None

def is_valid_name(property_name: str) -> bool:
    return property_name in CSSPROPERTIES


FONT_WEIGHT_CHOICES = {
    100: ["Thin", "Hairline", "100"],
    200: ["Extra Light", "Ultra Light", "200"],
    300: ["Light", "300"],
    400: ["Normal", "Regular", "400"],
    500: ["Medium", "500"],
    600: ["Semi Bold", "Demi Bold", "600"],
    700: ["Bold", "700"],
    800: ["Extra Bold", "Ultra Bold", "800"],
    900: ["Black", "Heavy", "900"],
}

def get_font_weight(value: str) -> int | None:
    # Clean whitespace and convert to lowercase for accurate matching
    target_value = value.strip().lower()
    
    # Iterate through the dictionary to check the name lists
    for weight_int, names in FONT_WEIGHT_CHOICES.items():
        # Compare lowercase versions of each name in the list
        if any(name.lower() == target_value for name in names):
            return weight_int
            
    return None
