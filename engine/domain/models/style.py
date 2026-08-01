from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


StyleSourceType = Literal[
    "rule",
    "inline",
    "attribute",
]


@dataclass(slots=True)
class StyleSource:
    """
    Referencia ligera a una declaración CSS que puede controlar una
    propiedad del elemento.
    """

    target_property: str
    declaration_name: str
    value: str
    source_type: StyleSourceType

    stylesheet_id: str | None = None
    selector: str | None = None
    origin: str = "regular"

    important: bool = False
    disabled: bool = False

    declaration_range: dict[str, int] | None = None
    style_range: dict[str, int] | None = None


@dataclass(slots=True)
class Stylesheet:
    """
    Información de una stylesheet perteneciente a un documento/frame.
    """

    stylesheet_id: str
    frame_id: str
    source_url: str

    origin: str = ""
    disabled: bool = False
    is_inline: bool = False
    is_mutable: bool = False
    is_constructed: bool = False
    loading_failed: bool = False

    owner_node: int | None = None
    parent_stylesheet_id: str | None = None

    original_text: str = ""
    current_text: str = ""


@dataclass(slots=True)
class StyleDocument:
    """
    Agrupa las stylesheets pertenecientes al mismo documento o frame.
    """

    frame_id: str
    stylesheets: dict[str, Stylesheet] = field(
        default_factory=dict
    )


class Styles:
    """
    Registro central de stylesheets y fuentes CSS asociadas a elementos.

    - Los documentos se agrupan por frameId.
    - Los elementos se identifican por backendNodeId.
    - Las fuentes se organizan por propiedad.
    """

    def __init__(self) -> None:
        self.documents: dict[str, StyleDocument] = {}

        self.sources_by_node: dict[
            int,
            dict[str, list[StyleSource]],
        ] = {}

        self.stylesheet_to_frame: dict[str, str] = {}

    def register_stylesheet(
        self,
        header: dict[str, Any],
    ) -> Stylesheet | None:
        stylesheet_id = header.get("styleSheetId")

        if not stylesheet_id:
            return None

        frame_id = str(header.get("frameId") or "")

        stylesheet = Stylesheet(
            stylesheet_id=stylesheet_id,
            frame_id=frame_id,
            source_url=str(
                header.get("sourceURL") or ""
            ),
            origin=str(
                header.get("origin") or ""
            ),
            disabled=bool(
                header.get("disabled", False)
            ),
            is_inline=bool(
                header.get("isInline", False)
            ),
            is_mutable=bool(
                header.get("isMutable", False)
            ),
            is_constructed=bool(
                header.get("isConstructed", False)
            ),
            loading_failed=bool(
                header.get("loadingFailed", False)
            ),
            owner_node=header.get("ownerNode"),
            parent_stylesheet_id=header.get(
                "parentStyleSheetId"
            ),
        )

        document = self.documents.setdefault(
            frame_id,
            StyleDocument(frame_id=frame_id),
        )

        document.stylesheets[
            stylesheet_id
        ] = stylesheet

        self.stylesheet_to_frame[
            stylesheet_id
        ] = frame_id

        return stylesheet

    def set_stylesheet_text(
        self,
        stylesheet_id: str,
        text: str,
        *,
        initialize: bool = False,
    ) -> None:
        stylesheet = self.get_stylesheet(
            stylesheet_id
        )

        if stylesheet is None:
            return

        if initialize and not stylesheet.original_text:
            stylesheet.original_text = text

        stylesheet.current_text = text

    def get_stylesheet(
        self,
        stylesheet_id: str,
    ) -> Stylesheet | None:
        frame_id = self.stylesheet_to_frame.get(
            stylesheet_id
        )

        if frame_id is None:
            return None

        document = self.documents.get(frame_id)

        if document is None:
            return None

        return document.stylesheets.get(
            stylesheet_id
        )

    def get_document_stylesheets(
        self,
        frame_id: str,
    ) -> tuple[Stylesheet, ...]:
        document = self.documents.get(frame_id)

        if document is None:
            return ()

        return tuple(
            document.stylesheets.values()
        )

    def register_element_sources(
        self,
        backend_node_id: int,
        matched_styles: dict[str, Any],
        property_names: set[str],
        *,
        include_inspector: bool = False,
    ) -> dict[str, list[StyleSource]]:
        sources = self.extract_property_sources(
            matched_styles=matched_styles,
            property_names=property_names,
            include_inspector=include_inspector,
        )

        self.sources_by_node[
            backend_node_id
        ] = sources

        return sources

    def get_sources(
        self,
        backend_node_id: int,
        property_name: str,
    ) -> tuple[StyleSource, ...]:
        return tuple(
            self.sources_by_node
            .get(backend_node_id, {})
            .get(property_name, ())
        )

    def clear(self) -> None:
        self.documents.clear()
        self.sources_by_node.clear()
        self.stylesheet_to_frame.clear()

    @staticmethod
    def extract_property_sources(
        matched_styles: dict[str, Any],
        property_names: set[str],
        *,
        include_inspector: bool = False,
    ) -> dict[str, list[StyleSource]]:
        """
        Extrae únicamente declaraciones relevantes para las propiedades
        analizadas del elemento.

        No incluye herencia, pseudo-elementos, user-agent, keyframes ni
        información adicional de CDP que no se utiliza para localizar el
        código fuente.
        """
        sources: dict[
            str,
            list[StyleSource],
        ] = {
            property_name: []
            for property_name in property_names
        }

        allowed_origins = {"regular"}

        if include_inspector:
            allowed_origins.add("inspector")

        def affected_properties(
            css_property: dict[str, Any],
        ) -> set[str]:
            affected = {
                str(css_property.get("name") or "")
            }

            affected.update(
                str(longhand.get("name") or "")
                for longhand
                in css_property.get(
                    "longhandProperties",
                    (),
                )
            )

            return affected & property_names

        def add_style_properties(
            style: dict[str, Any],
            *,
            source_type: StyleSourceType,
            selector: str | None,
            origin: str,
        ) -> None:
            for css_property in style.get(
                "cssProperties",
                (),
            ):
                if css_property.get("disabled", False):
                    continue

                if css_property.get("parsedOk") is False:
                    continue

                targets = affected_properties(
                    css_property
                )

                if not targets:
                    continue

                declaration_name = str(
                    css_property.get("name") or ""
                )

                declaration_value = str(
                    css_property.get("value") or ""
                )

                for target_property in targets:
                    sources[target_property].append(
                        StyleSource(
                            target_property=target_property,
                            declaration_name=(
                                declaration_name
                            ),
                            value=declaration_value,
                            source_type=source_type,
                            stylesheet_id=style.get(
                                "styleSheetId"
                            ),
                            selector=selector,
                            origin=origin,
                            important=bool(
                                css_property.get(
                                    "important",
                                    False,
                                )
                            ),
                            disabled=False,
                            declaration_range=(
                                css_property.get("range")
                            ),
                            style_range=style.get(
                                "range"
                            ),
                        )
                    )

        inline_style = matched_styles.get(
            "inlineStyle"
        )

        if inline_style:
            add_style_properties(
                inline_style,
                source_type="inline",
                selector=None,
                origin="regular",
            )

        attributes_style = matched_styles.get(
            "attributesStyle"
        )

        if attributes_style:
            add_style_properties(
                attributes_style,
                source_type="attribute",
                selector=None,
                origin="regular",
            )

        for matched_rule in matched_styles.get(
            "matchedCSSRules",
            (),
        ):
            rule = matched_rule.get("rule") or {}
            origin = str(
                rule.get("origin") or ""
            )

            if origin not in allowed_origins:
                continue

            style = rule.get("style") or {}
            selector_list = (
                rule.get("selectorList") or {}
            )

            selectors = selector_list.get(
                "selectors",
                (),
            )

            matching_indexes = matched_rule.get(
                "matchingSelectors",
                (),
            )

            matched_selector_texts = [
                str(selectors[index].get("text") or "")
                for index in matching_indexes
                if 0 <= index < len(selectors)
            ]

            selector = ", ".join(
                text
                for text in matched_selector_texts
                if text
            )

            if not selector:
                selector = str(
                    selector_list.get("text") or ""
                )

            add_style_properties(
                style,
                source_type="rule",
                selector=selector,
                origin=origin,
            )

        return {
            property_name: property_sources
            for property_name, property_sources
            in sources.items()
            if property_sources
        }
