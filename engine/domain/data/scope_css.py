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

print("¡ALERTA! Cargando datos en la memoria RAM por única vez...")
CSSPROPERTIES = MappingProxyType({
        "accent-color": CSSDATA(
            role="foreground",
            categories=["input"],
            shorthand=None,
            longhands=None,
            default_value=["auto"],
        ),
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
            default_value=["rgba(0, 0, 0, 0)"],
        ),
        "background-image": CSSDATA(
            role="background",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand= "background",
            longhands= None,
            default_value=["none"],
        ),
        "border": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand=None,
            longhands=["border-color"],
            default_value=["none", "0px"],
        ),
        "border-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border",
            longhands=["border-bottom-color", "border-left-color", "border-right-color", "border-top-color"],
            default_value=None,
        ),
        "border-bottom-color": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
            shorthand="border-color",
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
            default_value=None,
        ),
        "box-shadow": CSSDATA(
            role="foreground",
            categories=["main-surface", "container", "media", "composed", "input", "typography", "other"],
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
        "fill": CSSDATA(
            role="foreground",
            categories=["decoration"],
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
    }
)

def getAllShorthandProperties() -> tuple[str, ...]:
    shorthand_names = []
    for key in CSSPROPERTIES.keys():
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
    return CSSPROPERTIES[property_name].shorthand
