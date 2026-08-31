from __future__ import annotations

from itertools import batched
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import (
    Browser,
    BrowserContext,
    CDPSession,
    Page,
    Playwright,
    Request,
    sync_playwright,
)
from typing_extensions import Self

from engine.adapters.browser.server import StaticServer
from engine.domain.models.asset_records import AssetRecords
from engine.domain.models.style import Styles, StyleSource

_NAVIGATION_TIMEOUT = 30_000
_OPERATION_TIMEOUT = 10_000
_STYLE_MARKER_PREFIX = "GLOW_STYLESHEET:"


class PageBuilder:
    def __init__(
        self,
        server: StaticServer | None = None,
        styles: Styles | None = None,
        asset_records: AssetRecords | None = None,
        html_path: str | Path | None = None,
    ) -> None:
        self.html_path: Path | None = Path(html_path).resolve() if html_path is not None else None
        self.base_path: Path | None = None
        self.project_root: Path | None = None

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._cdp: CDPSession | None = None

        self._document: dict[str, Any] | None = None
        self._stylesheet_change_count = 0
        self._last_stylesheet_change_id: str | None = None
        self._theme_stylesheet_id: str | None = None
        self._server: StaticServer | None = server
        self.styles = styles if styles is not None else Styles()
        self.asset_records = (
            asset_records
            if asset_records is not None
            else AssetRecords()
        )

    def __enter__(self) -> Self:
        try:
            if self._server is None:
                raise RuntimeError("PageBuilder necesita un StaticServer activo.")
            if self.html_path is None:
                raise RuntimeError("PageBuilder necesita html_path.")

            self.html_path = self.html_path.resolve()
            self.base_path = self.html_path.parent
            self.project_root = self._server.root
            self._theme_stylesheet_id = None
            self._stylesheet_change_count = 0
            self._last_stylesheet_change_id = None

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
            )

            desktop_chrome = self._playwright.devices[
                "Desktop Chrome"
            ]

            self._context = self._browser.new_context(
                **desktop_chrome,
            )
            self._page = self._context.new_page()
            self._page.set_default_timeout(
                _OPERATION_TIMEOUT
            )
            self._page.set_default_navigation_timeout(
                _NAVIGATION_TIMEOUT
            )

            self._cdp = self._context.new_cdp_session(
                self._page
            )
            self._cdp.on(
                "CSS.styleSheetAdded",
                self._on_stylesheet_added,
            )
            self._cdp.on(
                "CSS.styleSheetChanged",
                self._on_stylesheet_changed,
            )
            self._page.on("requestfinished", self._handle_request)
            self._page.on("requestfailed", self._handle_request)

            self._cdp.send(
                "DOM.enable",
                {
                    "includeWhitespace": "all",
                },
            )
            self._cdp.send("CSS.enable")

            self._page.goto(
                self._server.url_for(self.html_path),
                wait_until="load",
            )

            self.wait_for_render_ready()
            self.asset_records.page_url = self.page_url
            self._document = self.get_full_document_node()
            self.cache_stylesheets()

            return self

        except Exception as exc:  # noqa: BLE001
            try:
                self.__exit__(type(exc), exc, exc.__traceback__)
            except Exception:
                pass
            raise RuntimeError(
                "PageBuilder initialization failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def _ensure_open(self) -> None:
        if (
            self._browser is None
            or not self._browser.is_connected()
            or self._context is None
            or self._page is None
            or self._page.is_closed()
            or self._cdp is None
        ):
            raise RuntimeError(
                "PageBuilder está cerrado o no fue inicializado."
            )

    @property
    def page_url(self) -> str:
        self._ensure_open()
        return self._page.url

    @property
    def viewport_size(self) -> dict[str, int]:
        self._ensure_open()

        return self._page.viewport_size or {
            "width": 0,
            "height": 0,
        }

    @property
    def document_root(self) -> dict[str, Any]:
        if self._document is None:
            raise RuntimeError("PageBuilder no tiene document_root.")
        return self._document

    def _on_stylesheet_added(
        self,
        event: dict[str, Any],
    ) -> None:
        header = event.get("header") or {}

        stylesheet = self.styles.register_stylesheet(
            header
        )
        
        if stylesheet is None:
            return

        if urlsplit(stylesheet.source_url).path.endswith("/glow.css"):
            self._theme_stylesheet_id = (
                stylesheet.stylesheet_id
            )
        
        if isinstance(stylesheet.owner_node, int):
            self.insert_stylesheet_marker(
                stylesheet.owner_node,
                stylesheet.stylesheet_id,
            )


    def _on_stylesheet_changed(
        self,
        event: dict[str, Any],
    ) -> None:
        stylesheet_id = event.get("styleSheetId")

        if stylesheet_id:
            self._stylesheet_change_count += 1
            self._last_stylesheet_change_id = str(
                stylesheet_id
            )

    def _handle_request(self, request: Request) -> None:
        try:
            response = request.response()
            failure = request.failure

            self.asset_records.add_network_information(
                url=(
                    response.url
                    if response is not None
                    else request.url
                ),
                timing = request.timing.get("startTime"),
                resource_type=request.resource_type,
                load_status=(
                    failure is None
                    and response is not None
                    and response.status < 400
                ),
                message=failure if failure is not None else response.status_text if response is not None else None,
            )
        except Exception as exc:
            raise RuntimeError(
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def wait_for_render_ready(self) -> None:
        self._ensure_open()

        try:
            self._page.wait_for_load_state("load")

            self._page.wait_for_function(
                "() => document.readyState === 'complete'"
            )

        except Exception as exc:
            raise RuntimeError(
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def get_full_document_node(
        self,
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        self._ensure_open()

        if self._document is not None and not refresh:
            return self._document

        try:
            root = self._cdp.send(
                "DOM.getDocument",
                {
                    "depth": -1,
                },
            ).get("root")

            if not root or not root.get("nodeId"):
                raise RuntimeError(
                    "DOM.getDocument no devolvió un nodo raíz."
                )

            self._document = root

            return self._document

        except Exception as exc:
            raise RuntimeError(
                "DOM document retrieval failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def wait_for_style_ready(self) -> None:
        """
        Espera hojas de estilo agregadas o actualizadas después
        de la carga inicial y permite dos ciclos de renderizado.
        """
        self._ensure_open()

        try:
            self._page.wait_for_function(
                """
                () => Array
                    .from(
                        document.querySelectorAll(
                            'link[rel~="stylesheet"]'
                        )
                    )
                    .filter(
                        (link) =>
                            !link.disabled
                            && (
                                !link.media
                                || matchMedia(link.media).matches
                            )
                    )
                    .every((link) => Boolean(link.sheet))
                """
            )

            self._page.evaluate(
                """
                () => new Promise((resolve) => {
                    requestAnimationFrame(() => {
                        requestAnimationFrame(resolve);
                    });
                })
                """
            )

        except Exception as exc:
            exception_type = type(exc).__name__

            raise RuntimeError(
                "Stylesheet readiness failed due to an unexpected "
                f"error [{exception_type}]: {exc}"
            ) from exc


    def extract_raw_snapshot(
        self,
        whitelist_styles: list[str],
    ) -> dict[str, Any]:
        """
        Captura el DOMSnapshot del documento actual.

        computedStyles únicamente controla qué estilos calculados se agregan
        al snapshot. No modifica el documento.
        """
        self._ensure_open()

        try:

            return self._cdp.send(
                "DOMSnapshot.captureSnapshot",
                {
                    "computedStyles": whitelist_styles,
                },
            )

        except Exception as exc:
            exception_type = type(exc).__name__

            raise RuntimeError(
                "DOMSnapshot capture failed due to an unexpected error "
                f"[{exception_type}]: {exc}"
            ) from exc

    def resolve_backend_node_id(
        self,
        backend_node_id: int,
    ) -> dict[any, any] | None:
        """
        Mantiene la resolución mediante DOM.describeNode y devuelve el nodeId
        frontend requerido por CSS.setEffectivePropertyValueForNode.
        """
        self._ensure_open()

        if not backend_node_id:
            return None

        try:

            node = self._cdp.send(
                "DOM.describeNode",
                {
                    "backendNodeId": int(backend_node_id),
                },
            ).get("node")

            return node

        except Exception as exc:
            exception_type = type(exc).__name__

            raise RuntimeError(
                "Backend node resolution failed due to an unexpected error "
                f"[{exception_type}]: {exc}"
            ) from exc

    
    def set_effective_value(
        self,
        backend_node_id: int,
        node_id: int,
        property_name: str,
        value: str,
        tag_name: str = "",
    ) -> dict[str, Any] | None:
        """
        Modifica una propiedad y determina dónde se realizó el cambio.

        Primero utiliza CSS.styleSheetChanged. Si no se modificó una hoja,
        consulta el estilo inline actual del nodo.
        """
        self._ensure_open()

        if not node_id:
            return None

        try:
            change_count = self._stylesheet_change_count

            self._cdp.send(
                "CSS.setEffectivePropertyValueForNode",
                {
                    "nodeId": int(node_id),
                    "propertyName": property_name,
                    "value": value,
                },
            )

            # Barrera dentro de la misma sesión CDP. Permite procesar los
            # eventos styleSheetChanged emitidos por la operación anterior.
            self._cdp.send(
                "Runtime.evaluate",
                {
                    "expression": "void 0",
                },
            )

            if (
                self._stylesheet_change_count
                != change_count
                and self._last_stylesheet_change_id
            ):
                stylesheet_id = self._last_stylesheet_change_id
                stylesheet = self.styles.get_stylesheet(
                    stylesheet_id
                )

                if stylesheet is None:
                    return {
                        "stylesheet_id": stylesheet_id,
                        "type": "unknown",
                        "changed": False,
                    }

                return {
                    "stylesheet_id": stylesheet_id,
                    "type": stylesheet.kind,
                    "changed": stylesheet.changed,
                }

            inline_styles = self.get_inline_styles_for_node(
                node_id
            )
            actual_property = self._find_inline_property(
                inline_styles,
                property_name,
            )

            if actual_property is not None:
                return {
                    "stylesheet_id": None,
                    "type": "inline",
                    "changed": True,
                }

            return {
                "stylesheet_id": None,
                "type": "unknown",
                "changed": False,
            }

        except Exception as exc:
            raise RuntimeError(
                "CSS property update failed for "
                f"<{tag_name or 'unknown'}> "
                f"backendNodeId={backend_node_id}, "
                f"nodeId={node_id}, "
                f"property={property_name}, "
                "due to an unexpected error "
                f"[{type(exc).__name__}]: {exc}"
            ) from exc

    def current_property_value(
        self,
        node_id: int,
        property_name: str,
    ) -> str | None:
        """
        Obtiene solamente la propiedad solicitada mediante getComputedStyle.

        Esto evita pedir todas las propiedades con
        CSS.getComputedStyleForNode en cada modificación.
        """
        self._ensure_open()

        if not node_id:
            return None

        object_id: str | None = None

        try:
            resolved = self._cdp.send(
                "DOM.resolveNode",
                {
                    "nodeId": int(node_id),
                },
            )

            object_id = resolved.get(
                "object",
                {},
            ).get("objectId")

            if not object_id:
                return None

            response = self._cdp.send(
                "Runtime.callFunctionOn",
                {
                    "objectId": object_id,
                    "functionDeclaration": """
                        function(propertyName) {
                            return window
                                .getComputedStyle(this)
                                .getPropertyValue(propertyName)
                                .trim();
                        }
                    """,
                    "arguments": [
                        {
                            "value": property_name,
                        },
                    ],
                    "returnByValue": True,
                },
            )

            result = response.get("result") or {}

            return result.get("value")

        except Exception as exc:
            exception_type = type(exc).__name__

            raise RuntimeError(
                "Current CSS value retrieval failed due to an unexpected "
                f"error [{exception_type}]: {exc}"
            ) from exc

        finally:
            # DOM.resolveNode crea un objeto remoto. Liberarlo evita acumular
            # referencias si este método se ejecuta muchas veces.
            if object_id:
                try:
                    self._cdp.send(
                        "Runtime.releaseObject",
                        {
                            "objectId": object_id,
                        },
                    )
                except Exception:
                    pass

    def set_color_scheme(self) -> bool:
        self._ensure_open()

        try:
            applied = self._page.evaluate(
                """
                async () => {
                    let meta = document.querySelector(
                        'meta[name="color-scheme"]'
                    );

                    if (!meta) {
                        meta = document.createElement("meta");
                        meta.name = "color-scheme";
                        document.head.appendChild(meta);
                    }

                    meta.content = "dark";

                    await new Promise((resolve) => {
                        requestAnimationFrame(() => {
                            requestAnimationFrame(resolve);
                        });
                    });

                    return (
                        document.querySelector(
                            'meta[name="color-scheme"]'
                        )?.content === "dark"
                    );
                }
                """
            )

            if applied is not True:
                raise RuntimeError(
                    "color-scheme no quedó configurado."
                )

            return True

        except Exception as exc:
            raise RuntimeError(
                "Color scheme configuration failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc


    def set_data_theme(self) -> bool:
        self._ensure_open()

        try:
            applied = self._page.evaluate(
                """
                async () => {
                    const root = document.documentElement;

                    if (!root) {
                        return false;
                    }

                    root.setAttribute(
                        "data-theme",
                        "glow"
                    );

                    await new Promise((resolve) => {
                        requestAnimationFrame(() => {
                            requestAnimationFrame(resolve);
                        });
                    });

                    return (
                        root.getAttribute("data-theme")
                        === "glow"
                    );
                }
                """
            )

            if applied is not True:
                raise RuntimeError(
                    "data-theme no quedó configurado."
                )

            return True

        except Exception as exc:
            raise RuntimeError(
                "Theme attribute configuration failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def set_theme_link(self) -> bool:
        self._ensure_open()

        try:
            stylesheet_href = self._page.evaluate(
                """
                async ({ href, timeoutMs }) => {
                    const absoluteHref = new URL(
                        href,
                        document.baseURI
                    ).href;

                    let link = Array
                        .from(
                            document.querySelectorAll(
                                'link[rel~="stylesheet"]'
                            )
                        )
                        .find((candidate) => {
                            return (
                                candidate.dataset.glowTheme
                                    === "true"
                                || candidate.href
                                    === absoluteHref
                            );
                        });

                    if (!link) {
                        link = document.createElement("link");
                        link.rel = "stylesheet";
                        link.dataset.glowTheme = "true";
                    }

                    link.disabled = false;

                    const alreadyLoaded = Boolean(
                        link.isConnected
                        && link.href === absoluteHref
                        && link.sheet
                    );

                    if (!alreadyLoaded) {
                        await new Promise(
                            (resolve, reject) => {
                                let settled = false;

                                const finish = (error) => {
                                    if (settled) {
                                        return;
                                    }

                                    settled = true;
                                    clearTimeout(timeoutId);

                                    link.removeEventListener(
                                        "load",
                                        onLoad
                                    );

                                    link.removeEventListener(
                                        "error",
                                        onError
                                    );

                                    if (error) {
                                        reject(error);
                                    } else {
                                        resolve();
                                    }
                                };

                                const onLoad = () => finish();

                                const onError = () => finish(
                                    new Error(
                                        "No se pudo cargar "
                                        + absoluteHref
                                    )
                                );

                                const timeoutId = setTimeout(
                                    () => finish(
                                        new Error(
                                            "La carga de glow.css "
                                            + "excedió el tiempo."
                                        )
                                    ),
                                    timeoutMs
                                );

                                link.addEventListener(
                                    "load",
                                    onLoad,
                                    { once: true }
                                );

                                link.addEventListener(
                                    "error",
                                    onError,
                                    { once: true }
                                );

                                if (
                                    link.href
                                    !== absoluteHref
                                ) {
                                    link.href = href;
                                }

                                if (!link.isConnected) {
                                    document.head.appendChild(
                                        link
                                    );
                                }
                            }
                        );
                    }

                    if (
                        link.parentElement !== document.head
                        || link !== document.head.lastElementChild
                    ) {
                        document.head.appendChild(link);
                    }

                    await new Promise((resolve) => {
                        requestAnimationFrame(() => {
                            requestAnimationFrame(resolve);
                        });
                    });

                    if (
                        !link.sheet
                        || !Array
                            .from(document.styleSheets)
                            .includes(link.sheet)
                    ) {
                        throw new Error(
                            "glow.css no quedó registrado "
                            + "en document.styleSheets."
                        );
                    }

                    return link.href;
                }
                """,
                {
                    "href": "glow.css",
                    "timeoutMs": _OPERATION_TIMEOUT,
                },
            )

            self._cdp.send(
                "Runtime.evaluate",
                {
                    "expression": "void 0",
                },
            )

            if self._theme_stylesheet_id is None:
                self._theme_stylesheet_id = next(
                    (
                        stylesheet.stylesheet_id
                        for stylesheet
                        in self.styles.stylesheets.values()
                        if stylesheet.source_url
                        == stylesheet_href
                    ),
                    None,
                )

            if self._theme_stylesheet_id is None:
                raise RuntimeError(
                    "No se pudo localizar el styleSheetId de glow.css."
                )

            theme_text = self.get_stylesheet_text(
                self._theme_stylesheet_id
            )

            self.styles.set_stylesheet_text(
                self._theme_stylesheet_id,
                theme_text,
                initialize=True,
            )

            return True

        except Exception as exc:
            raise RuntimeError(
                "Theme stylesheet loading failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def set_theme_stylesheet_text(
        self,
        css_content: str,
    ) -> None:
        self._ensure_open()

        if self._theme_stylesheet_id is None:
            raise RuntimeError(
                "glow.css todavía no tiene styleSheetId."
            )

        try:
            self.set_stylesheet_text(
                self._theme_stylesheet_id,
                css_content,
            )

        except Exception as exc:
            raise RuntimeError(
                "Theme stylesheet update failed due to an unexpected "
                f"error [{type(exc).__name__}]: {exc}"
            ) from exc

    def set_stylesheet_text(
        self,
        stylesheet_id: str,
        css_content: str,
    ) -> None:
        self._ensure_open()

        if not stylesheet_id:
            return

        try:
            self._cdp.send(
                "CSS.setStyleSheetText",
                {
                    "styleSheetId": stylesheet_id,
                    "text": css_content,
                },
            )

            self.styles.set_stylesheet_text(
                stylesheet_id,
                css_content,
            )

        except Exception as exc:
            raise RuntimeError(
                "Stylesheet update failed due to an unexpected "
                f"error [{type(exc).__name__}]: {exc}"
            ) from exc

    def get_background_colors(
        self,
        node_id: int,
    ) -> dict[str, Any]:
        """
        Obtiene los colores de fondo y las métricas tipográficas calculadas
        para un nodo.

        Siempre devuelve un diccionario con:
            - background_colors
            - font_size
            - font_weight
        """
        self._ensure_open()

        if not node_id:
            return {
                "background_colors": [],
                "font_size": "",
                "font_weight": "",
            }

        try:
            response = self._cdp.send(
                "CSS.getBackgroundColors",
                {
                    "nodeId": int(node_id),
                },
            )

            return {
                "background_colors": response.get(
                    "backgroundColors",
                    [],
                ),
                "font_size": response.get(
                    "computedFontSize",
                    "",
                ),
                "font_weight": response.get(
                    "computedFontWeight",
                    "",
                ),
            }

        except Exception as exc:
            exception_type = type(exc).__name__

            raise RuntimeError(
                "CSS.getBackgroundColors failed due to an unexpected "
                f"error [{exception_type}]: {exc}"
            ) from exc


    def get_box_model(
        self,
        backend_node_id: int,
    ) -> dict[str, Any]:
        """
        Obtiene el diccionario completo de box model con los quads resueltos.

        Devuelve un dict vacío cuando el nodo no tiene una caja visual.
        """
        self._ensure_open()

        if not backend_node_id:
            return {}

        try:
            model = self._cdp.send(
                "DOM.getBoxModel",
                {
                    "backendNodeId": int(backend_node_id),
                },
            ).get("model") or {}

            width = float(model.get("width") or 0)
            height = float(model.get("height") or 0)
            if width <= 0 or height <= 0:
                return {}

            for name in ("content", "padding", "border", "margin"):
                coordinates = model.get(name) or []
                model[name] = [
                    (float(x), float(y))
                    for x, y in batched(coordinates, 2)
                ]

            model["width"] = width
            model["height"] = height
            model.pop("shapeOutside", None)

            return model

        except Exception as exc:
            # Este error es normal para nodos sin representación visual,
            # como display: none o algunos nodos internos.
            if "Could not compute box model" in str(exc):
                return {}

            exception_type = type(exc).__name__

            raise RuntimeError(
                "DOM.getBoxModel failed due to an unexpected "
                f"error [{exception_type}]: {exc}"
            ) from exc


    def get_computed_styles_for_node(
        self,
        node_id: int,
    ) -> dict[str, str]:
        """
        Obtiene todos los estilos calculados del nodo como un diccionario.
        """
        self._ensure_open()

        if not node_id:
            return {}

        try:
            response = self._cdp.send(
                "CSS.getComputedStyleForNode",
                {
                    "nodeId": int(node_id),
                },
            )

            return {
                css_property["name"]: css_property.get(
                    "value",
                    "",
                )
                for css_property in response.get(
                    "computedStyle",
                    [],
                )
                if css_property.get("name")
            }

        except Exception as exc:
            exception_type = type(exc).__name__

            raise RuntimeError(
                "CSS.getComputedStyleForNode failed due to an unexpected "
                f"error [{exception_type}]: {exc}"
            ) from exc

    def capture_fullpage_screenshot(
        self,
        output_path: str | Path,
    ) -> Path:
        self._ensure_open()

        output = Path(output_path)

        try:
            output.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self.wait_for_style_ready()

            self._page.screenshot(
                path=output,
                full_page=True,
                animations="disabled",
                caret="hide",
                scale="css"
            )

            return output

        except Exception as exc:
            raise RuntimeError(
                "Full-page screenshot failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def get_matched_styles(
        self,
        node_id: int,
    ) -> dict[str, Any]:
        self._ensure_open()

        try:
            return self._cdp.send(
                "CSS.getMatchedStylesForNode",
                {
                    "nodeId": int(node_id),
                },
            )

        except Exception as exc:
            raise RuntimeError(
                "Matched styles retrieval failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def set_attribute_value(
        self,
        node_id: int,
        attribute_name: str,
        value: str,
    ) -> str | None:
        """
        Establece el valor de un atributo HTML o SVG y devuelve el valor
        registrado finalmente en el nodo.

        Ejemplos de atributos:
            src
            href
            xlink:href
            data
            fill
            stroke
        """
        self._ensure_open()

        if not node_id or not attribute_name:
            return None

        try:
            self._cdp.send(
                "DOM.setAttributeValue",
                {
                    "nodeId": int(node_id),
                    "name": attribute_name,
                    "value": value,
                },
            )

            attributes = self._cdp.send(
                "DOM.getAttributes",
                {
                    "nodeId": int(node_id),
                },
            ).get("attributes", [])

            return next((value for name, value in batched(attributes, 2) if name == attribute_name), None)

        except Exception as exc:
            raise RuntimeError(
                "Attribute update failed for "
                f"nodeId={node_id}, "
                f"attribute={attribute_name}, "
                "due to an unexpected error "
                f"[{type(exc).__name__}]: {exc}"
            ) from exc

    def get_inline_styles_for_node(
        self,
        node_id: int,
    ) -> dict[str, Any]:
        self._ensure_open()

        try:
            return self._cdp.send(
                "CSS.getInlineStylesForNode",
                {
                    "nodeId": int(node_id),
                },
            )

        except Exception as exc:
            raise RuntimeError(
                "Inline styles retrieval failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    @staticmethod
    def _find_inline_property(
        inline_styles: dict[str, Any],
        property_name: str,
    ) -> dict[str, Any] | None:
        style = inline_styles.get("inlineStyle") or {}

        for css_property in (
            style.get("cssProperties") or []
        ):
            if css_property.get("disabled"):
                continue

            if css_property.get("name") != property_name:
                continue

            return {
                "source_type": "inline",
                "value": css_property.get("value", ""),
                "important": bool(
                    css_property.get("important", False)
                ),
                "range": css_property.get("range"),
                "style_range": style.get("range"),
            }

        return None

    def get_stylesheet_text(
        self,
        stylesheet_id: str,
    ) -> str:
        self._ensure_open()

        try:
            response = self._cdp.send(
                "CSS.getStyleSheetText",
                {
                    "styleSheetId": stylesheet_id,
                },
            )

            return response.get("text", "")

        except Exception as exc:
            raise RuntimeError(
                "Stylesheet retrieval failed due to an unexpected "
                f"error [{type(exc).__name__}]: {exc}"
            ) from exc

    def cache_stylesheets(self) -> None:
        """
        Guarda el texto original y actual de todas las hojas cuyo contenido
        puede recuperarse mediante CDP.
        """
        self._ensure_open()

        try:
            for stylesheet in self.styles.stylesheets.values():
                try:
                    text = self.get_stylesheet_text(
                        stylesheet.stylesheet_id
                    )
                except RuntimeError:
                    continue

                self.styles.set_stylesheet_text(
                    stylesheet.stylesheet_id,
                    text,
                    initialize=True,
                )

        except Exception as exc:
            raise RuntimeError(
                "Stylesheet caching failed due to an unexpected "
                f"error [{type(exc).__name__}]: {exc}"
            ) from exc

    def register_element_style_sources(
        self,
        *,
        backend_node_id: int,
        node_id: int,
        property_names: set[str],
    ) -> dict[str, list[StyleSource]]:
        """
        Obtiene los estilos coincidentes y conserva solamente las fuentes
        relacionadas con las propiedades analizadas del elemento.
        """
        self._ensure_open()

        try:
            matched_styles = self.get_matched_styles(
                node_id
            )

            return self.styles.register_element_sources(
                backend_node_id=backend_node_id,
                matched_styles=matched_styles,
                property_names=property_names,
            )

        except Exception as exc:
            raise RuntimeError(
                "Element style source registration failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def get_main_frame_id(self) -> str:
        """
        Obtiene el frameId del documento principal.

        Se utiliza para excluir stylesheets pertenecientes a iframes u otros
        documentos que no corresponden al HTML recuperado con get_outer_html().
        """
        self._ensure_open()

        try:
            response = self._cdp.send(
                "Page.getFrameTree"
            )

            frame_tree = response.get("frameTree") or {}
            frame = frame_tree.get("frame") or {}
            frame_id = str(frame.get("id") or "")

            if not frame_id:
                raise RuntimeError(
                    "Page.getFrameTree no devolvió el frame principal."
                )

            return frame_id

        except Exception as exc:
            raise RuntimeError(
                "Main frame retrieval failed due to an unexpected "
                f"error [{type(exc).__name__}]: {exc}"
            ) from exc


    def get_outer_html(self) -> str:
        """
        Recupera el HTML completo del documento actualmente cargado.

        DOM.getOuterHTML no suele incluir el DOCTYPE; este se agrega
        posteriormente durante el formateo.
        """
        self._ensure_open()

        try:
            outer_html = self._cdp.send(
                "DOM.getOuterHTML",
                {
                    "nodeId": self.document_root.get("nodeId", None),
                },
            ).get("outerHTML", "")

            if not str(outer_html).strip():
                raise RuntimeError(
                    "DOM.getOuterHTML no devolvió contenido."
                )

            return str(outer_html)

        except Exception as exc:
            raise RuntimeError(
                "Outer HTML retrieval failed due to an unexpected "
                f"error [{type(exc).__name__}]: {exc}"
            ) from exc

    def query_selector(
        self,
        selector: str,
        node_id: int | None = None,
    ) -> int | None:
        """
        Busca el primer nodo que coincida con el selector CSS.

        Si node_id no se proporciona, la búsqueda inicia desde el nodo raíz
        del documento.

        Retorna el nodeId encontrado o None cuando no existe coincidencia.
        """
        self._ensure_open()

        if not selector.strip():
            return None

        try:

            return self._cdp.send(
                "DOM.querySelector",
                {
                    "nodeId": node_id if node_id is not None else self.document_root.get("nodeId", None),
                    "selector": selector.strip(),
                },
            ).get("nodeId", None)

        except Exception as exc:
            raise RuntimeError(
                "DOM query selector failed for "
                f"selector={selector!r}, "
                "due to an unexpected error "
                f"[{type(exc).__name__}]: {exc}"
            ) from exc

    def insert_stylesheet_marker(
        self,
        backend_node_id: int,
        identifier: str,
    ) -> bool:
        self._ensure_open()
        try:
            resolved = self._cdp.send(
                "DOM.resolveNode",
                {
                    "backendNodeId": backend_node_id,
                },
            )

            remote_object = resolved.get("object") or {}
            object_id = remote_object.get("objectId")

            if object_id is None:
                return False

            result = self._cdp.send(
                "Runtime.callFunctionOn",
                {
                    "objectId": object_id,
                    "functionDeclaration": """
                        function (prefix, identifier) {
                            if (!this.parentNode) {
                                return false;
                            }

                            const markerValue =
                                `${prefix}${identifier}`;

                            const previous =
                                this.previousSibling;

                            if (
                                previous?.nodeType ===
                                    Node.COMMENT_NODE
                                && previous.nodeValue ===
                                    markerValue
                            ) {
                                return true;
                            }

                            const comment =
                                new Comment(markerValue);

                            this.parentNode.insertBefore(
                                comment,
                                this
                            );

                            return true;
                        }
                    """,
                    "arguments": [
                        {
                            "value":
                                _STYLE_MARKER_PREFIX
                        },
                        {
                            "value": identifier
                        },
                    ],
                    "returnByValue": True,
                },
            )

            return bool(
                result
                .get("result", {})
                .get("value")
            )

        except Exception as exc:
            raise RuntimeError(
                "Outer HTML retrieval failed due to an unexpected "
                f"error [{type(exc).__name__}]: {exc}"
            ) from exc

    def __exit__(self, exc_type, exc, traceback) -> bool:
        page = self._page
        context = self._context
        browser = self._browser
        playwright = self._playwright
        close_errors: list[str] = []

        self._cdp = None
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._document = None
        self._theme_stylesheet_id = None
        self._stylesheet_change_count = 0
        self._last_stylesheet_change_id = None

        if page is not None and not page.is_closed():
            try:
                page.close()
            except Exception as close_exc:
                close_errors.append(
                    f"page [{type(close_exc).__name__}]: {close_exc}"
                )

        if context is not None:
            try:
                context.close()
            except Exception as close_exc:
                close_errors.append(
                    f"context [{type(close_exc).__name__}]: {close_exc}"
                )

        if browser is not None and browser.is_connected():
            try:
                browser.close()
            except Exception as close_exc:
                close_errors.append(
                    f"browser [{type(close_exc).__name__}]: {close_exc}"
                )

        if playwright is not None:
            try:
                playwright.stop()
            except Exception as close_exc:
                close_errors.append(
                    f"playwright [{type(close_exc).__name__}]: {close_exc}"
                )

        if close_errors and exc_type is None:
            raise RuntimeError(
                "PageBuilder close failed: " + "; ".join(close_errors)
            )

        return False
