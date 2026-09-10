from dataclasses import dataclass
from types import MappingProxyType


# =====================================================================
# 1. ESTRUCTURA ULTRA-LIGERA
# =====================================================================
@dataclass(frozen=True)
class HTMLDATA:
    __slots__ = ("category",)
    category: str


# La categoría "media" conserva el mismo identificador usado en
# scope-css.py, aunque en el esquema visual aparezca como "Image".
HTMLELEMENTS = MappingProxyType(
    {
        "a": HTMLDATA(category="typography"),
        "abbr": HTMLDATA(category="typography"),
        "address": HTMLDATA(category="composed"),
        "article": HTMLDATA(category="container"),
        "aside": HTMLDATA(category="container"),
        "audio": HTMLDATA(category="media"),
        "b": HTMLDATA(category="typography"),
        "bdi": HTMLDATA(category="typography"),
        "bdo": HTMLDATA(category="typography"),
        "blockquote": HTMLDATA(category="composed"),
        "body": HTMLDATA(category="main-surface"),
        "br": HTMLDATA(category="typography"),
        "button": HTMLDATA(category="composed"),
        "canvas": HTMLDATA(category="media"),
        "caption": HTMLDATA(category="typography"),
        "cite": HTMLDATA(category="typography"),
        "code": HTMLDATA(category="typography"),
        "col": HTMLDATA(category="container"),
        "colgroup": HTMLDATA(category="container"),
        "data": HTMLDATA(category="typography"),
        "datalist": HTMLDATA(category="input"),
        "dd": HTMLDATA(category="composed"),
        "del": HTMLDATA(category="typography"),
        "dfn": HTMLDATA(category="typography"),
        "div": HTMLDATA(category="container"),
        "dl": HTMLDATA(category="composed"),
        "dt": HTMLDATA(category="composed"),
        "em": HTMLDATA(category="typography"),
        "embed": HTMLDATA(category="media"),
        "fieldset": HTMLDATA(category="container"),
        "figcaption": HTMLDATA(category="typography"),
        "figure": HTMLDATA(category="composed"),
        "footer": HTMLDATA(category="container"),
        "foreignobject": HTMLDATA(category="decoration"),
        "form": HTMLDATA(category="container"),
        "h1": HTMLDATA(category="typography"),
        "h2": HTMLDATA(category="typography"),
        "h3": HTMLDATA(category="typography"),
        "h4": HTMLDATA(category="typography"),
        "h5": HTMLDATA(category="typography"),
        "h6": HTMLDATA(category="typography"),
        "header": HTMLDATA(category="container"),
        "hgroup": HTMLDATA(category="composed"),
        "hr": HTMLDATA(category="media"),
        "html": HTMLDATA(category="main-surface"),
        "i": HTMLDATA(category="typography"),
        "iframe": HTMLDATA(category="media"),
        "img": HTMLDATA(category="media"),
        "input": HTMLDATA(category="input"),
        "ins": HTMLDATA(category="typography"),
        "kbd": HTMLDATA(category="typography"),
        "label": HTMLDATA(category="typography"),
        "legend": HTMLDATA(category="typography"),
        "li": HTMLDATA(category="composed"),
        "main": HTMLDATA(category="container"),
        "mark": HTMLDATA(category="typography"),
        "menu": HTMLDATA(category="container"),
        "meter": HTMLDATA(category="composed"),
        "nav": HTMLDATA(category="container"),
        "object": HTMLDATA(category="media"),
        "ol": HTMLDATA(category="composed"),
        "optgroup": HTMLDATA(category="input"),
        "option": HTMLDATA(category="input"),
        "output": HTMLDATA(category="composed"),
        "p": HTMLDATA(category="typography"),
        "picture": HTMLDATA(category="media"),
        "pre": HTMLDATA(category="typography"),
        "progress": HTMLDATA(category="composed"),
        "q": HTMLDATA(category="typography"),
        "rp": HTMLDATA(category="typography"),
        "rt": HTMLDATA(category="typography"),
        "ruby": HTMLDATA(category="typography"),
        "s": HTMLDATA(category="typography"),
        "samp": HTMLDATA(category="typography"),
        "search": HTMLDATA(category="container"),
        "section": HTMLDATA(category="container"),
        "select": HTMLDATA(category="input"),
        "selectedcontent": HTMLDATA(category="input"),
        "small": HTMLDATA(category="typography"),
        "span": HTMLDATA(category="typography"),
        "strong": HTMLDATA(category="typography"),
        "sub": HTMLDATA(category="typography"),
        "summary": HTMLDATA(category="composed"),
        "sup": HTMLDATA(category="typography"),
        "svg": HTMLDATA(category="decoration"),
        "table": HTMLDATA(category="container"),
        "tbody": HTMLDATA(category="container"),
        "td": HTMLDATA(category="composed"),
        "textarea": HTMLDATA(category="input"),
        "tfoot": HTMLDATA(category="container"),
        "th": HTMLDATA(category="composed"),
        "thead": HTMLDATA(category="container"),
        "time": HTMLDATA(category="typography"),
        "tr": HTMLDATA(category="container"),
        "u": HTMLDATA(category="typography"),
        "ul": HTMLDATA(category="composed"),
        "var": HTMLDATA(category="typography"),
        "video": HTMLDATA(category="media"),
        "wbr": HTMLDATA(category="typography"),
        "circle": HTMLDATA(category="decoration"),
        "defs": HTMLDATA(category="decoration"),
        "ellipse": HTMLDATA(category="decoration"),
        "g": HTMLDATA(category="decoration"),
        "line": HTMLDATA(category="decoration"),
        "path": HTMLDATA(category="decoration"),
        "polygon": HTMLDATA(category="decoration"),
        "polyline": HTMLDATA(category="decoration"),
        "rect": HTMLDATA(category="decoration"),
        "symbol": HTMLDATA(category="decoration"),
        "text": HTMLDATA(category="decoration"),
        "use": HTMLDATA(category="decoration"),
        "details": HTMLDATA(category="composed"),
        "dialog": HTMLDATA(category="container"),
    }
)


def get_html_element_category(element_name: object) -> str | None:
    element_data = HTMLELEMENTS.get(str(element_name or "").strip().lower())
    return element_data.category if element_data is not None else None

def get_html_elements_by_category(category: str) -> tuple[str, ...]:
    normalized = str(category or "").strip().lower()
    return tuple(
        tag for tag, data in HTMLELEMENTS.items() if data.category == normalized
    )