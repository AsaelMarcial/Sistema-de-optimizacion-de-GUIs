from __future__ import annotations


from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

 
class HtmlElementScopeGroup(StrEnum):
    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE_VISIBLE = "out_of_scope_visible"
    IGNORED = "ignored"


class HtmlElementId(StrEnum):
    A = "a"
    ABBR = "abbr"
    ADDRESS = "address"
    ARTICLE = "article"
    ASIDE = "aside"
    AUDIO = "audio"
    B = "b"
    BDI = "bdi"
    BDO = "bdo"
    BLOCKQUOTE = "blockquote"
    BODY = "body"
    BR = "br"
    BUTTON = "button"
    CANVAS = "canvas"
    CAPTION = "caption"
    CITE = "cite"
    CODE = "code"
    COL = "col"
    COLGROUP = "colgroup"
    DATA = "data"
    DATALIST = "datalist"
    DD = "dd"
    DEL = "del"
    DFN = "dfn"
    DIV = "div"
    DL = "dl"
    DT = "dt"
    EM = "em"
    EMBED = "embed"
    FIELDSET = "fieldset"
    FIGCAPTION = "figcaption"
    FIGURE = "figure"
    FOOTER = "footer"
    FORM = "form"
    H1 = "h1"
    H2 = "h2"
    H3 = "h3"
    H4 = "h4"
    H5 = "h5"
    H6 = "h6"
    HEADER = "header"
    HGROUP = "hgroup"
    HR = "hr"
    HTML = "html"
    I = "i"
    IFRAME = "iframe"
    IMG = "img"
    INPUT = "input"
    INS = "ins"
    KBD = "kbd"
    LABEL = "label"
    LEGEND = "legend"
    LI = "li"
    MAIN = "main"
    MARK = "mark"
    MENU = "menu"
    METER = "meter"
    NAV = "nav"
    OBJECT = "object"
    OL = "ol"
    OPTGROUP = "optgroup"
    OPTION = "option"
    OUTPUT = "output"
    P = "p"
    PICTURE = "picture"
    PRE = "pre"
    PROGRESS = "progress"
    Q = "q"
    RP = "rp"
    RT = "rt"
    RUBY = "ruby"
    S = "s"
    SAMP = "samp"
    SEARCH = "search"
    SECTION = "section"
    SELECT = "select"
    SELECTEDCONTENT = "selectedcontent"
    SMALL = "small"
    SPAN = "span"
    STRONG = "strong"
    SUB = "sub"
    SUMMARY = "summary"
    SUP = "sup"
    SVG = "svg"
    TABLE = "table"
    TBODY = "tbody"
    TD = "td"
    TEXTAREA = "textarea"
    TFOOT = "tfoot"
    TH = "th"
    THEAD = "thead"
    TIME = "time"
    TR = "tr"
    U = "u"
    UL = "ul"
    VAR = "var"
    VIDEO = "video"
    WBR = "wbr"


@dataclass(frozen=True, slots=True)
class HtmlElementSpec:
    element_id: HtmlElementId
    scope_group: HtmlElementScopeGroup
    description: str
    categories: tuple[str, ...]
    is_visible: bool = True
    capture_text: bool = True
    capture_children: bool = True


def _spec(
    element_id: HtmlElementId,
    scope_group: HtmlElementScopeGroup,
    description: str,
    *categories: str,
    is_visible: bool = True,
    capture_text: bool = True,
    capture_children: bool = True,
) -> HtmlElementSpec:
    return HtmlElementSpec(
        element_id=element_id,
        scope_group=scope_group,
        description=description,
        categories=categories,
        is_visible=is_visible,
        capture_text=capture_text,
        capture_children=capture_children,
    )


HTML_ELEMENT_SPECS: tuple[HtmlElementSpec, ...] = (
    _spec(HtmlElementId.HTML, HtmlElementScopeGroup.IN_SCOPE, "Document root", "document", "structural"),
    _spec(HtmlElementId.BODY, HtmlElementScopeGroup.IN_SCOPE, "Document body", "document", "structural"),
    _spec(HtmlElementId.HEADER, HtmlElementScopeGroup.IN_SCOPE, "Header section", "structural", "landmark"),
    _spec(HtmlElementId.FOOTER, HtmlElementScopeGroup.IN_SCOPE, "Footer section", "structural", "landmark"),
    _spec(HtmlElementId.MAIN, HtmlElementScopeGroup.IN_SCOPE, "Main content", "structural", "landmark"),
    _spec(HtmlElementId.SECTION, HtmlElementScopeGroup.IN_SCOPE, "Section", "structural"),
    _spec(HtmlElementId.ARTICLE, HtmlElementScopeGroup.IN_SCOPE, "Article", "structural"),
    _spec(HtmlElementId.ASIDE, HtmlElementScopeGroup.IN_SCOPE, "Aside", "structural"),
    _spec(HtmlElementId.NAV, HtmlElementScopeGroup.IN_SCOPE, "Navigation", "structural", "landmark"),
    _spec(HtmlElementId.SEARCH, HtmlElementScopeGroup.IN_SCOPE, "Search region", "structural", "landmark"),
    _spec(HtmlElementId.HGROUP, HtmlElementScopeGroup.IN_SCOPE, "Heading group", "structural", "heading"),
    _spec(HtmlElementId.ADDRESS, HtmlElementScopeGroup.IN_SCOPE, "Contact information", "text", "structural"),
    _spec(HtmlElementId.MENU, HtmlElementScopeGroup.IN_SCOPE, "Menu", "structural", "interactive"),
    _spec(HtmlElementId.DIV, HtmlElementScopeGroup.IN_SCOPE, "Generic container", "structural"),
    _spec(HtmlElementId.SPAN, HtmlElementScopeGroup.IN_SCOPE, "Inline container", "text"),
    _spec(HtmlElementId.P, HtmlElementScopeGroup.IN_SCOPE, "Paragraph", "text"),
    _spec(HtmlElementId.A, HtmlElementScopeGroup.IN_SCOPE, "Hyperlink", "text", "interactive"),
    _spec(HtmlElementId.ABBR, HtmlElementScopeGroup.IN_SCOPE, "Abbreviation", "text"),
    _spec(HtmlElementId.EM, HtmlElementScopeGroup.IN_SCOPE, "Emphasis", "text"),
    _spec(HtmlElementId.STRONG, HtmlElementScopeGroup.IN_SCOPE, "Strong emphasis", "text"),
    _spec(HtmlElementId.SMALL, HtmlElementScopeGroup.IN_SCOPE, "Small text", "text"),
    _spec(HtmlElementId.S, HtmlElementScopeGroup.IN_SCOPE, "Strikethrough text", "text"),
    _spec(HtmlElementId.CITE, HtmlElementScopeGroup.IN_SCOPE, "Citation", "text"),
    _spec(HtmlElementId.Q, HtmlElementScopeGroup.IN_SCOPE, "Inline quotation", "text"),
    _spec(HtmlElementId.DFN, HtmlElementScopeGroup.IN_SCOPE, "Definition term", "text"),
    _spec(HtmlElementId.CODE, HtmlElementScopeGroup.IN_SCOPE, "Code fragment", "text"),
    _spec(HtmlElementId.VAR, HtmlElementScopeGroup.IN_SCOPE, "Variable name", "text"),
    _spec(HtmlElementId.SAMP, HtmlElementScopeGroup.IN_SCOPE, "Sample output", "text"),
    _spec(HtmlElementId.KBD, HtmlElementScopeGroup.IN_SCOPE, "Keyboard input", "text"),
    _spec(HtmlElementId.SUB, HtmlElementScopeGroup.IN_SCOPE, "Subscript", "text"),
    _spec(HtmlElementId.SUP, HtmlElementScopeGroup.IN_SCOPE, "Superscript", "text"),
    _spec(HtmlElementId.I, HtmlElementScopeGroup.IN_SCOPE, "Alternate voice text", "text"),
    _spec(HtmlElementId.B, HtmlElementScopeGroup.IN_SCOPE, "Bold offset text", "text"),
    _spec(HtmlElementId.U, HtmlElementScopeGroup.IN_SCOPE, "Unarticulated annotation", "text"),
    _spec(HtmlElementId.MARK, HtmlElementScopeGroup.IN_SCOPE, "Marked text", "text"),
    _spec(HtmlElementId.BDI, HtmlElementScopeGroup.IN_SCOPE, "Bidirectional isolation", "text"),
    _spec(HtmlElementId.BDO, HtmlElementScopeGroup.IN_SCOPE, "Bidirectional override", "text"),
    _spec(HtmlElementId.DATA, HtmlElementScopeGroup.IN_SCOPE, "Machine-readable data", "text"),
    _spec(HtmlElementId.TIME, HtmlElementScopeGroup.IN_SCOPE, "Time value", "text"),
    _spec(HtmlElementId.RUBY, HtmlElementScopeGroup.IN_SCOPE, "Ruby annotation", "text"),
    _spec(HtmlElementId.RT, HtmlElementScopeGroup.IN_SCOPE, "Ruby text", "text"),
    _spec(HtmlElementId.RP, HtmlElementScopeGroup.IN_SCOPE, "Ruby fallback parentheses", "text"),
    _spec(HtmlElementId.BR, HtmlElementScopeGroup.IN_SCOPE, "Line break", "text", capture_text=False, capture_children=False),
    _spec(HtmlElementId.WBR, HtmlElementScopeGroup.IN_SCOPE, "Word break opportunity", "text", capture_text=False, capture_children=False),
    _spec(HtmlElementId.INS, HtmlElementScopeGroup.IN_SCOPE, "Inserted text", "text"),
    _spec(HtmlElementId.DEL, HtmlElementScopeGroup.IN_SCOPE, "Deleted text", "text"),
    _spec(HtmlElementId.BUTTON, HtmlElementScopeGroup.IN_SCOPE, "Button control", "interactive", "form"),
    _spec(HtmlElementId.INPUT, HtmlElementScopeGroup.IN_SCOPE, "Input control", "interactive", "form"),
    _spec(HtmlElementId.TEXTAREA, HtmlElementScopeGroup.IN_SCOPE, "Textarea control", "interactive", "form"),
    _spec(HtmlElementId.SELECT, HtmlElementScopeGroup.IN_SCOPE, "Select control", "interactive", "form"),
    _spec(HtmlElementId.OPTGROUP, HtmlElementScopeGroup.IN_SCOPE, "Option group", "interactive", "form"),
    _spec(HtmlElementId.OPTION, HtmlElementScopeGroup.IN_SCOPE, "Select option", "interactive", "form"),
    _spec(HtmlElementId.DATALIST, HtmlElementScopeGroup.IN_SCOPE, "Datalist", "interactive", "form"),
    _spec(HtmlElementId.LABEL, HtmlElementScopeGroup.IN_SCOPE, "Form label", "text", "form"),
    _spec(HtmlElementId.OUTPUT, HtmlElementScopeGroup.IN_SCOPE, "Form output", "text", "form"),
    _spec(HtmlElementId.METER, HtmlElementScopeGroup.IN_SCOPE, "Meter", "interactive", "form"),
    _spec(HtmlElementId.PROGRESS, HtmlElementScopeGroup.IN_SCOPE, "Progress indicator", "interactive", "form"),
    _spec(HtmlElementId.FORM, HtmlElementScopeGroup.IN_SCOPE, "Form", "structural", "form"),
    _spec(HtmlElementId.FIELDSET, HtmlElementScopeGroup.IN_SCOPE, "Fieldset", "structural", "form"),
    _spec(HtmlElementId.LEGEND, HtmlElementScopeGroup.IN_SCOPE, "Legend", "text", "form"),
    _spec(HtmlElementId.SELECTEDCONTENT, HtmlElementScopeGroup.IN_SCOPE, "Selected content", "interactive", "form"),
    _spec(HtmlElementId.TABLE, HtmlElementScopeGroup.IN_SCOPE, "Table", "table"),
    _spec(HtmlElementId.CAPTION, HtmlElementScopeGroup.IN_SCOPE, "Table caption", "table", "text"),
    _spec(HtmlElementId.COLGROUP, HtmlElementScopeGroup.IN_SCOPE, "Table column group", "table"),
    _spec(HtmlElementId.COL, HtmlElementScopeGroup.IN_SCOPE, "Table column", "table", capture_text=False, capture_children=False),
    _spec(HtmlElementId.THEAD, HtmlElementScopeGroup.IN_SCOPE, "Table head", "table"),
    _spec(HtmlElementId.TBODY, HtmlElementScopeGroup.IN_SCOPE, "Table body", "table"),
    _spec(HtmlElementId.TFOOT, HtmlElementScopeGroup.IN_SCOPE, "Table foot", "table"),
    _spec(HtmlElementId.TR, HtmlElementScopeGroup.IN_SCOPE, "Table row", "table"),
    _spec(HtmlElementId.TH, HtmlElementScopeGroup.IN_SCOPE, "Table header cell", "table", "text"),
    _spec(HtmlElementId.TD, HtmlElementScopeGroup.IN_SCOPE, "Table cell", "table", "text"),
    _spec(HtmlElementId.UL, HtmlElementScopeGroup.IN_SCOPE, "Unordered list", "list"),
    _spec(HtmlElementId.OL, HtmlElementScopeGroup.IN_SCOPE, "Ordered list", "list"),
    _spec(HtmlElementId.LI, HtmlElementScopeGroup.IN_SCOPE, "List item", "list"),
    _spec(HtmlElementId.DL, HtmlElementScopeGroup.IN_SCOPE, "Description list", "list"),
    _spec(HtmlElementId.DT, HtmlElementScopeGroup.IN_SCOPE, "Description term", "list", "text"),
    _spec(HtmlElementId.DD, HtmlElementScopeGroup.IN_SCOPE, "Description details", "list", "text"),
    _spec(HtmlElementId.H1, HtmlElementScopeGroup.IN_SCOPE, "Heading 1", "text", "heading"),
    _spec(HtmlElementId.H2, HtmlElementScopeGroup.IN_SCOPE, "Heading 2", "text", "heading"),
    _spec(HtmlElementId.H3, HtmlElementScopeGroup.IN_SCOPE, "Heading 3", "text", "heading"),
    _spec(HtmlElementId.H4, HtmlElementScopeGroup.IN_SCOPE, "Heading 4", "text", "heading"),
    _spec(HtmlElementId.H5, HtmlElementScopeGroup.IN_SCOPE, "Heading 5", "text", "heading"),
    _spec(HtmlElementId.H6, HtmlElementScopeGroup.IN_SCOPE, "Heading 6", "text", "heading"),
    _spec(HtmlElementId.BLOCKQUOTE, HtmlElementScopeGroup.IN_SCOPE, "Block quote", "text"),
    _spec(HtmlElementId.PRE, HtmlElementScopeGroup.IN_SCOPE, "Preformatted block", "text"),
    _spec(HtmlElementId.FIGURE, HtmlElementScopeGroup.IN_SCOPE, "Figure", "structural"),
    _spec(HtmlElementId.FIGCAPTION, HtmlElementScopeGroup.IN_SCOPE, "Figure caption", "text"),
    _spec(HtmlElementId.HR, HtmlElementScopeGroup.IN_SCOPE, "Thematic break", "decorative"),
    _spec(HtmlElementId.SUMMARY, HtmlElementScopeGroup.IN_SCOPE, "Disclosure summary", "interactive", "text"),
    _spec(HtmlElementId.IMG, HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE, "Image", "media", capture_text=False),
    _spec(HtmlElementId.PICTURE, HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE, "Responsive image container", "media", capture_text=False),
    _spec(HtmlElementId.VIDEO, HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE, "Video", "media", capture_text=False),
    _spec(HtmlElementId.AUDIO, HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE, "Audio", "media", capture_text=False),
    _spec(HtmlElementId.CANVAS, HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE, "Canvas", "media", capture_text=False),
    _spec(HtmlElementId.IFRAME, HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE, "Embedded frame", "media", capture_text=False),
    _spec(HtmlElementId.EMBED, HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE, "Embedded content", "media", capture_text=False),
    _spec(HtmlElementId.OBJECT, HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE, "Embedded object", "media", capture_text=False),
    _spec(HtmlElementId.SVG, HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE, "Scalable vector graphics", "media", capture_text=False),
)


HTML_ELEMENTS_BY_ID: Mapping[str, HtmlElementSpec] = {
    spec.element_id.value: spec for spec in HTML_ELEMENT_SPECS
}

MEDIA_METADATA_ONLY_TAGS: frozenset[str] = frozenset({"area", "map", "source", "track"})

IGNORED_HTML_TAGS: frozenset[str] = frozenset(
    {
        "area",
        "base",
        "head",
        "link",
        "map",
        "meta",
        "noscript",
        "param",
        "script",
        "slot",
        "source",
        "style",
        "template",
        "title",
        "track",
    }
)


def get_snapshot_included_html_elements() -> tuple[HtmlElementSpec, ...]:
    return tuple(
        spec
        for spec in HTML_ELEMENT_SPECS
        if spec.scope_group in {
            HtmlElementScopeGroup.IN_SCOPE,
            HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        }
    )
