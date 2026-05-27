from enum import StrEnum
from types import MappingProxyType


class HtmlElementScopeGroup(StrEnum):
    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE_VISIBLE = "out_of_scope_visible"
    IGNORED = "ignored"


def _normalize_html_tag_name(value: object) -> str:
    return str(value or "").strip().lower()


class HtmlElementId(StrEnum):
    scope_group: HtmlElementScopeGroup
    description: str
    categories: tuple[str, ...]
    is_visible: bool
    capture_text: bool
    capture_children: bool

    def __new__(
        cls,
        value: str,
        scope_group: HtmlElementScopeGroup,
        description: str,
        categories: tuple[str, ...],
        is_visible: bool = True,
        capture_text: bool = True,
        capture_children: bool = True,
    ) -> "HtmlElementId":
        self = str.__new__(cls, value)
        self._value_ = value
        return self

    def __init__(
        self,
        _value: str,
        scope_group: HtmlElementScopeGroup,
        description: str,
        categories: tuple[str, ...],
        is_visible: bool = True,
        capture_text: bool = True,
        capture_children: bool = True,
    ) -> None:
        self.scope_group = scope_group
        self.description = description
        self.categories = categories
        self.is_visible = is_visible
        self.capture_text = capture_text
        self.capture_children = capture_children

    A = (
        'a',
        HtmlElementScopeGroup.IN_SCOPE,
        'Hyperlink',
        ('text', 'interactive'),
        True,
        True,
        True,
    )
    ABBR = (
        'abbr',
        HtmlElementScopeGroup.IN_SCOPE,
        'Abbreviation',
        ('text',),
        True,
        True,
        True,
    )
    ADDRESS = (
        'address',
        HtmlElementScopeGroup.IN_SCOPE,
        'Contact information',
        ('text', 'structural'),
        True,
        True,
        True,
    )
    ARTICLE = (
        'article',
        HtmlElementScopeGroup.IN_SCOPE,
        'Article',
        ('structural',),
        True,
        True,
        True,
    )
    ASIDE = (
        'aside',
        HtmlElementScopeGroup.IN_SCOPE,
        'Aside',
        ('structural',),
        True,
        True,
        True,
    )
    AUDIO = (
        'audio',
        HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        'Audio',
        ('media',),
        True,
        False,
        True,
    )
    B = (
        'b',
        HtmlElementScopeGroup.IN_SCOPE,
        'Bold offset text',
        ('text',),
        True,
        True,
        True,
    )
    BDI = (
        'bdi',
        HtmlElementScopeGroup.IN_SCOPE,
        'Bidirectional isolation',
        ('text',),
        True,
        True,
        True,
    )
    BDO = (
        'bdo',
        HtmlElementScopeGroup.IN_SCOPE,
        'Bidirectional override',
        ('text',),
        True,
        True,
        True,
    )
    BLOCKQUOTE = (
        'blockquote',
        HtmlElementScopeGroup.IN_SCOPE,
        'Block quote',
        ('text',),
        True,
        True,
        True,
    )
    BODY = (
        'body',
        HtmlElementScopeGroup.IN_SCOPE,
        'Document body',
        ('document', 'structural'),
        True,
        True,
        True,
    )
    BR = (
        'br',
        HtmlElementScopeGroup.IN_SCOPE,
        'Line break',
        ('text',),
        True,
        False,
        False,
    )
    BUTTON = (
        'button',
        HtmlElementScopeGroup.IN_SCOPE,
        'Button control',
        ('interactive', 'form'),
        True,
        True,
        True,
    )
    CANVAS = (
        'canvas',
        HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        'Canvas',
        ('media',),
        True,
        False,
        True,
    )
    CAPTION = (
        'caption',
        HtmlElementScopeGroup.IN_SCOPE,
        'Table caption',
        ('table', 'text'),
        True,
        True,
        True,
    )
    CITE = (
        'cite',
        HtmlElementScopeGroup.IN_SCOPE,
        'Citation',
        ('text',),
        True,
        True,
        True,
    )
    CODE = (
        'code',
        HtmlElementScopeGroup.IN_SCOPE,
        'Code fragment',
        ('text',),
        True,
        True,
        True,
    )
    COL = (
        'col',
        HtmlElementScopeGroup.IN_SCOPE,
        'Table column',
        ('table',),
        True,
        False,
        False,
    )
    COLGROUP = (
        'colgroup',
        HtmlElementScopeGroup.IN_SCOPE,
        'Table column group',
        ('table',),
        True,
        True,
        True,
    )
    DATA = (
        'data',
        HtmlElementScopeGroup.IN_SCOPE,
        'Machine-readable data',
        ('text',),
        True,
        True,
        True,
    )
    DATALIST = (
        'datalist',
        HtmlElementScopeGroup.IN_SCOPE,
        'Datalist',
        ('interactive', 'form'),
        True,
        True,
        True,
    )
    DD = (
        'dd',
        HtmlElementScopeGroup.IN_SCOPE,
        'Description details',
        ('list', 'text'),
        True,
        True,
        True,
    )
    DEL = (
        'del',
        HtmlElementScopeGroup.IN_SCOPE,
        'Deleted text',
        ('text',),
        True,
        True,
        True,
    )
    DFN = (
        'dfn',
        HtmlElementScopeGroup.IN_SCOPE,
        'Definition term',
        ('text',),
        True,
        True,
        True,
    )
    DIV = (
        'div',
        HtmlElementScopeGroup.IN_SCOPE,
        'Generic container',
        ('structural',),
        True,
        True,
        True,
    )
    DL = (
        'dl',
        HtmlElementScopeGroup.IN_SCOPE,
        'Description list',
        ('list',),
        True,
        True,
        True,
    )
    DT = (
        'dt',
        HtmlElementScopeGroup.IN_SCOPE,
        'Description term',
        ('list', 'text'),
        True,
        True,
        True,
    )
    EM = (
        'em',
        HtmlElementScopeGroup.IN_SCOPE,
        'Emphasis',
        ('text',),
        True,
        True,
        True,
    )
    EMBED = (
        'embed',
        HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        'Embedded content',
        ('media',),
        True,
        False,
        True,
    )
    FIELDSET = (
        'fieldset',
        HtmlElementScopeGroup.IN_SCOPE,
        'Fieldset',
        ('structural', 'form'),
        True,
        True,
        True,
    )
    FIGCAPTION = (
        'figcaption',
        HtmlElementScopeGroup.IN_SCOPE,
        'Figure caption',
        ('text',),
        True,
        True,
        True,
    )
    FIGURE = (
        'figure',
        HtmlElementScopeGroup.IN_SCOPE,
        'Figure',
        ('structural',),
        True,
        True,
        True,
    )
    FOOTER = (
        'footer',
        HtmlElementScopeGroup.IN_SCOPE,
        'Footer section',
        ('structural', 'landmark'),
        True,
        True,
        True,
    )
    FORM = (
        'form',
        HtmlElementScopeGroup.IN_SCOPE,
        'Form',
        ('structural', 'form'),
        True,
        True,
        True,
    )
    H1 = (
        'h1',
        HtmlElementScopeGroup.IN_SCOPE,
        'Heading 1',
        ('text', 'heading'),
        True,
        True,
        True,
    )
    H2 = (
        'h2',
        HtmlElementScopeGroup.IN_SCOPE,
        'Heading 2',
        ('text', 'heading'),
        True,
        True,
        True,
    )
    H3 = (
        'h3',
        HtmlElementScopeGroup.IN_SCOPE,
        'Heading 3',
        ('text', 'heading'),
        True,
        True,
        True,
    )
    H4 = (
        'h4',
        HtmlElementScopeGroup.IN_SCOPE,
        'Heading 4',
        ('text', 'heading'),
        True,
        True,
        True,
    )
    H5 = (
        'h5',
        HtmlElementScopeGroup.IN_SCOPE,
        'Heading 5',
        ('text', 'heading'),
        True,
        True,
        True,
    )
    H6 = (
        'h6',
        HtmlElementScopeGroup.IN_SCOPE,
        'Heading 6',
        ('text', 'heading'),
        True,
        True,
        True,
    )
    HEADER = (
        'header',
        HtmlElementScopeGroup.IN_SCOPE,
        'Header section',
        ('structural', 'landmark'),
        True,
        True,
        True,
    )
    HGROUP = (
        'hgroup',
        HtmlElementScopeGroup.IN_SCOPE,
        'Heading group',
        ('structural', 'heading'),
        True,
        True,
        True,
    )
    HR = (
        'hr',
        HtmlElementScopeGroup.IN_SCOPE,
        'Thematic break',
        ('decorative',),
        True,
        True,
        True,
    )
    HTML = (
        'html',
        HtmlElementScopeGroup.IN_SCOPE,
        'Document root',
        ('document', 'structural'),
        True,
        True,
        True,
    )
    I = (
        'i',
        HtmlElementScopeGroup.IN_SCOPE,
        'Alternate voice text',
        ('text',),
        True,
        True,
        True,
    )
    IFRAME = (
        'iframe',
        HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        'Embedded frame',
        ('media',),
        True,
        False,
        True,
    )
    IMG = (
        'img',
        HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        'Image',
        ('media',),
        True,
        False,
        True,
    )
    INPUT = (
        'input',
        HtmlElementScopeGroup.IN_SCOPE,
        'Input control',
        ('interactive', 'form'),
        True,
        True,
        True,
    )
    INS = (
        'ins',
        HtmlElementScopeGroup.IN_SCOPE,
        'Inserted text',
        ('text',),
        True,
        True,
        True,
    )
    KBD = (
        'kbd',
        HtmlElementScopeGroup.IN_SCOPE,
        'Keyboard input',
        ('text',),
        True,
        True,
        True,
    )
    LABEL = (
        'label',
        HtmlElementScopeGroup.IN_SCOPE,
        'Form label',
        ('text', 'form'),
        True,
        True,
        True,
    )
    LEGEND = (
        'legend',
        HtmlElementScopeGroup.IN_SCOPE,
        'Legend',
        ('text', 'form'),
        True,
        True,
        True,
    )
    LI = (
        'li',
        HtmlElementScopeGroup.IN_SCOPE,
        'List item',
        ('list',),
        True,
        True,
        True,
    )
    MAIN = (
        'main',
        HtmlElementScopeGroup.IN_SCOPE,
        'Main content',
        ('structural', 'landmark'),
        True,
        True,
        True,
    )
    MARK = (
        'mark',
        HtmlElementScopeGroup.IN_SCOPE,
        'Marked text',
        ('text',),
        True,
        True,
        True,
    )
    MENU = (
        'menu',
        HtmlElementScopeGroup.IN_SCOPE,
        'Menu',
        ('structural', 'interactive'),
        True,
        True,
        True,
    )
    METER = (
        'meter',
        HtmlElementScopeGroup.IN_SCOPE,
        'Meter',
        ('interactive', 'form'),
        True,
        True,
        True,
    )
    NAV = (
        'nav',
        HtmlElementScopeGroup.IN_SCOPE,
        'Navigation',
        ('structural', 'landmark'),
        True,
        True,
        True,
    )
    OBJECT = (
        'object',
        HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        'Embedded object',
        ('media',),
        True,
        False,
        True,
    )
    OL = (
        'ol',
        HtmlElementScopeGroup.IN_SCOPE,
        'Ordered list',
        ('list',),
        True,
        True,
        True,
    )
    OPTGROUP = (
        'optgroup',
        HtmlElementScopeGroup.IN_SCOPE,
        'Option group',
        ('interactive', 'form'),
        True,
        True,
        True,
    )
    OPTION = (
        'option',
        HtmlElementScopeGroup.IN_SCOPE,
        'Select option',
        ('interactive', 'form'),
        True,
        True,
        True,
    )
    OUTPUT = (
        'output',
        HtmlElementScopeGroup.IN_SCOPE,
        'Form output',
        ('text', 'form'),
        True,
        True,
        True,
    )
    P = (
        'p',
        HtmlElementScopeGroup.IN_SCOPE,
        'Paragraph',
        ('text',),
        True,
        True,
        True,
    )
    PICTURE = (
        'picture',
        HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        'Responsive image container',
        ('media',),
        True,
        False,
        True,
    )
    PRE = (
        'pre',
        HtmlElementScopeGroup.IN_SCOPE,
        'Preformatted block',
        ('text',),
        True,
        True,
        True,
    )
    PROGRESS = (
        'progress',
        HtmlElementScopeGroup.IN_SCOPE,
        'Progress indicator',
        ('interactive', 'form'),
        True,
        True,
        True,
    )
    Q = (
        'q',
        HtmlElementScopeGroup.IN_SCOPE,
        'Inline quotation',
        ('text',),
        True,
        True,
        True,
    )
    RP = (
        'rp',
        HtmlElementScopeGroup.IN_SCOPE,
        'Ruby fallback parentheses',
        ('text',),
        True,
        True,
        True,
    )
    RT = (
        'rt',
        HtmlElementScopeGroup.IN_SCOPE,
        'Ruby text',
        ('text',),
        True,
        True,
        True,
    )
    RUBY = (
        'ruby',
        HtmlElementScopeGroup.IN_SCOPE,
        'Ruby annotation',
        ('text',),
        True,
        True,
        True,
    )
    S = (
        's',
        HtmlElementScopeGroup.IN_SCOPE,
        'Strikethrough text',
        ('text',),
        True,
        True,
        True,
    )
    SAMP = (
        'samp',
        HtmlElementScopeGroup.IN_SCOPE,
        'Sample output',
        ('text',),
        True,
        True,
        True,
    )
    SEARCH = (
        'search',
        HtmlElementScopeGroup.IN_SCOPE,
        'Search region',
        ('structural', 'landmark'),
        True,
        True,
        True,
    )
    SECTION = (
        'section',
        HtmlElementScopeGroup.IN_SCOPE,
        'Section',
        ('structural',),
        True,
        True,
        True,
    )
    SELECT = (
        'select',
        HtmlElementScopeGroup.IN_SCOPE,
        'Select control',
        ('interactive', 'form'),
        True,
        True,
        True,
    )
    SELECTEDCONTENT = (
        'selectedcontent',
        HtmlElementScopeGroup.IN_SCOPE,
        'Selected content',
        ('interactive', 'form'),
        True,
        True,
        True,
    )
    SMALL = (
        'small',
        HtmlElementScopeGroup.IN_SCOPE,
        'Small text',
        ('text',),
        True,
        True,
        True,
    )
    SPAN = (
        'span',
        HtmlElementScopeGroup.IN_SCOPE,
        'Inline container',
        ('text',),
        True,
        True,
        True,
    )
    STRONG = (
        'strong',
        HtmlElementScopeGroup.IN_SCOPE,
        'Strong emphasis',
        ('text',),
        True,
        True,
        True,
    )
    SUB = (
        'sub',
        HtmlElementScopeGroup.IN_SCOPE,
        'Subscript',
        ('text',),
        True,
        True,
        True,
    )
    SUMMARY = (
        'summary',
        HtmlElementScopeGroup.IN_SCOPE,
        'Disclosure summary',
        ('interactive', 'text'),
        True,
        True,
        True,
    )
    SUP = (
        'sup',
        HtmlElementScopeGroup.IN_SCOPE,
        'Superscript',
        ('text',),
        True,
        True,
        True,
    )
    SVG = (
        'svg',
        HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        'Scalable vector graphics',
        ('media',),
        True,
        False,
        True,
    )
    TABLE = (
        'table',
        HtmlElementScopeGroup.IN_SCOPE,
        'Table',
        ('table',),
        True,
        True,
        True,
    )
    TBODY = (
        'tbody',
        HtmlElementScopeGroup.IN_SCOPE,
        'Table body',
        ('table',),
        True,
        True,
        True,
    )
    TD = (
        'td',
        HtmlElementScopeGroup.IN_SCOPE,
        'Table cell',
        ('table', 'text'),
        True,
        True,
        True,
    )
    TEXTAREA = (
        'textarea',
        HtmlElementScopeGroup.IN_SCOPE,
        'Textarea control',
        ('interactive', 'form'),
        True,
        True,
        True,
    )
    TFOOT = (
        'tfoot',
        HtmlElementScopeGroup.IN_SCOPE,
        'Table foot',
        ('table',),
        True,
        True,
        True,
    )
    TH = (
        'th',
        HtmlElementScopeGroup.IN_SCOPE,
        'Table header cell',
        ('table', 'text'),
        True,
        True,
        True,
    )
    THEAD = (
        'thead',
        HtmlElementScopeGroup.IN_SCOPE,
        'Table head',
        ('table',),
        True,
        True,
        True,
    )
    TIME = (
        'time',
        HtmlElementScopeGroup.IN_SCOPE,
        'Time value',
        ('text',),
        True,
        True,
        True,
    )
    TR = (
        'tr',
        HtmlElementScopeGroup.IN_SCOPE,
        'Table row',
        ('table',),
        True,
        True,
        True,
    )
    U = (
        'u',
        HtmlElementScopeGroup.IN_SCOPE,
        'Unarticulated annotation',
        ('text',),
        True,
        True,
        True,
    )
    UL = (
        'ul',
        HtmlElementScopeGroup.IN_SCOPE,
        'Unordered list',
        ('list',),
        True,
        True,
        True,
    )
    VAR = (
        'var',
        HtmlElementScopeGroup.IN_SCOPE,
        'Variable name',
        ('text',),
        True,
        True,
        True,
    )
    VIDEO = (
        'video',
        HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        'Video',
        ('media',),
        True,
        False,
        True,
    )
    WBR = (
        'wbr',
        HtmlElementScopeGroup.IN_SCOPE,
        'Word break opportunity',
        ('text',),
        True,
        False,
        False,
    )


HTML_ELEMENT_SPECS: tuple[HtmlElementId, ...] = tuple(HtmlElementId)
HTML_ELEMENTS_BY_ID = MappingProxyType(
    {spec.value: spec for spec in HTML_ELEMENT_SPECS}
)

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


def get_snapshot_included_html_elements() -> tuple[HtmlElementId, ...]:
    return tuple(
        spec
        for spec in HTML_ELEMENT_SPECS
        if spec.scope_group in {
            HtmlElementScopeGroup.IN_SCOPE,
            HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE,
        }
    )


def get_html_element(value: object) -> HtmlElementId | None:
    normalized = _normalize_html_tag_name(value)
    if not normalized:
        return None
    return HTML_ELEMENTS_BY_ID.get(normalized)
