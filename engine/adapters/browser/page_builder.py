from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from playwright.sync_api import (
    Browser,
    BrowserContext,
    CDPSession,
    Page,
    Playwright,
    sync_playwright,
)

from engine.domain.models.style import Styles, StyleSource, Stylesheet, StyleDocument, StyleSourceType


_LOCALHOST = "http://127.0.0.1"
_DEFAULT_PORT = 8000
_NAVIGATION_TIMEOUT = 30_000
_OPERATION_TIMEOUT = 10_000


class _ReusableStaticServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class _QuietStaticHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return


class PageBuilder:
    def __init__(self) -> None:
        self.html_path: Path | None = None
        self.base_path: Path | None = None

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._cdp: CDPSession | None = None

        self._document_root: dict[str, Any] | None = None
        self._stylesheet_changes: list[str] = []
        self._theme_stylesheet_id: str | None = None
        self._server: _ReusableStaticServer | None = None
        self._server_thread: threading.Thread | None = None
        self._port = _DEFAULT_PORT
        self.styles = Styles()

        self._init_playwright()

    @property
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
    def theme_stylesheet_id(self) -> str | None:
        return self._theme_stylesheet_id

    @property
    def document_root(self) -> dict[str, Any] | None:
        return (
            dict(self._document_root)
            if self._document_root is not None
            else None
        )

    @property
    def current_url(self) -> str:
        self._ensure_open
        assert self._page is not None

        return self._page.url

    @property
    def is_open(self) -> bool:
        return (
            self._browser is not None
            and self._browser.is_connected()
            and self._context is not None
            and self._page is not None
            and not self._page.is_closed()
            and self._cdp is not None
        )

    def _init_playwright(self) -> None:
        try:
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

            self._cdp.send("DOM.enable")
            self._cdp.send("CSS.enable")

        except Exception as exc:
            try:
                self.close()
            except Exception:
                pass

            raise RuntimeError(
                "Playwright initialization failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def _restart_server(self, directory: Path) -> None:
        self._stop_server()

        handler = functools.partial(
            _QuietStaticHandler,
            directory=str(directory),
        )

        for port in (_DEFAULT_PORT, 0):
            try:
                self._server = _ReusableStaticServer(
                    ("127.0.0.1", port),
                    handler,
                )
                break
            except OSError:
                self._server = None

        if self._server is None:
            raise RuntimeError(
                "No se pudo iniciar el servidor local para PageBuilder."
            )

        self._port = int(self._server.server_address[1])
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._server_thread.start()

    def _stop_server(self) -> None:
        server = self._server
        thread = self._server_thread

        self._server = None
        self._server_thread = None

        if server is not None:
            server.shutdown()
            server.server_close()

        if thread is not None and thread.is_alive():
            thread.join(timeout=2)

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


    def _on_stylesheet_changed(
        self,
        event: dict[str, Any],
    ) -> None:
        stylesheet_id = event.get("styleSheetId")

        if stylesheet_id:
            self._stylesheet_changes.append(
                stylesheet_id
            )

    def load_page(
    self,
    html_path: str | Path,
    ) -> None:
        self._ensure_open
        assert self._page is not None

        target = Path(html_path).resolve()

        if not target.is_file():
            raise FileNotFoundError(
                f"HTML no encontrado: {target}"
            )

        self.html_path = target
        self.base_path = target.parent
        self._restart_server(target.parent)

        self._document_root = None
        self._theme_stylesheet_id = None
        self._stylesheet_changes.clear()
        self.styles.clear()

        page_url = f"{_LOCALHOST}:{self._port}/{quote(target.name)}"

        try:
            response = self._page.goto(
                page_url,
                wait_until="load",
            )

            if response is None:
                raise RuntimeError(
                    "La navegación no devolvió una respuesta."
                )

            response.finished()

            if response.status >= 400:
                raise RuntimeError(
                    f"HTTP {response.status}: "
                    f"{response.request.method} "
                    f"{response.url}"
                )

            self.wait_for_render_ready()
            self.get_full_document_node()
            self.cache_stylesheets()

        except Exception as exc:
            raise RuntimeError(
                "Page loading failed due to an unexpected "
                f"error [{type(exc).__name__}]: {exc}"
            ) from exc

    def wait_for_render_ready(self) -> None:
        self._ensure_open
        assert self._page is not None

        try:
            self._page.wait_for_load_state("load")

            self._page.wait_for_function(
                "() => document.readyState === 'complete'"
            )

            ready = self._page.evaluate(
                """
                async (timeoutMs) => {
                    const waitForImage = (image) => {
                        if (image.complete) {
                            return Promise.resolve();
                        }

                        return new Promise((resolve, reject) => {
                            const finish = (error) => {
                                image.removeEventListener(
                                    "load",
                                    onLoad
                                );

                                image.removeEventListener(
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
                                    "No se pudo cargar la imagen: "
                                    + (
                                        image.currentSrc
                                        || image.src
                                    )
                                )
                            );

                            image.addEventListener(
                                "load",
                                onLoad,
                                { once: true }
                            );

                            image.addEventListener(
                                "error",
                                onError,
                                { once: true }
                            );
                        });
                    };

                    const prepare = async () => {
                        if (document.fonts?.ready) {
                            await document.fonts.ready;
                        }

                        const images = Array.from(
                            document.images
                        );

                        await Promise.all(
                            images.map(waitForImage)
                        );

                        const brokenImages = images.filter(
                            (image) =>
                                image.complete
                                && image.naturalWidth === 0
                        );

                        if (brokenImages.length > 0) {
                            throw new Error(
                                "Una o más imágenes no se cargaron."
                            );
                        }

                        await Promise.all(
                            images.map(async (image) => {
                                if (
                                    typeof image.decode
                                    !== "function"
                                ) {
                                    return;
                                }

                                try {
                                    await image.decode();
                                } catch (error) {
                                    if (
                                        image.naturalWidth === 0
                                    ) {
                                        throw error;
                                    }
                                }
                            })
                        );

                        await new Promise((resolve) => {
                            requestAnimationFrame(() => {
                                requestAnimationFrame(resolve);
                            });
                        });

                        return (
                            document.readyState === "complete"
                        );
                    };

                    return Promise.race([
                        prepare(),

                        new Promise((_, reject) => {
                            setTimeout(
                                () => reject(
                                    new Error(
                                        "La preparación del render "
                                        + `excedió ${timeoutMs} ms.`
                                    )
                                ),
                                timeoutMs
                            );
                        })
                    ]);
                }
                """,
                _OPERATION_TIMEOUT,
            )

            if ready is not True:
                raise RuntimeError(
                    "El documento no quedó listo."
                )

        except Exception as exc:
            raise RuntimeError(
                "Render readiness failed due to an unexpected "
                f"error [{type(exc).__name__}]: {exc}"
            ) from exc

    def get_full_document_node(
        self,
    ) -> dict[str, Any]:
        self._ensure_open
        assert self._cdp is not None

        if self._document_root is not None:
            return dict(self._document_root)

        try:
            response = self._cdp.send(
                "DOM.getDocument",
                {
                    "depth": -1,
                    "pierce": True,
                },
            )

            root = response.get("root") or {}

            if not root:
                raise RuntimeError(
                    "DOM.getDocument no devolvió un nodo raíz."
                )

            self._document_root = root

            return dict(root)

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
        self._ensure_open
        assert self._page is not None

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
        self._ensure_open
        assert self._cdp is not None

        try:
            if self._document_root is None:
                self.get_full_document_node()

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
        self._ensure_open
        assert self._cdp is not None

        if not backend_node_id:
            return None

        try:
            if self._document_root is None:
                self.get_full_document_node()

            response = self._cdp.send(
                "DOM.describeNode",
                {
                    "backendNodeId": int(backend_node_id),
                },
            )

            node = response.get("node") or {}

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
        self._ensure_open
        assert self._cdp is not None

        if not node_id:
            return None

        try:
            expected_sources = self.styles.get_sources(
                backend_node_id,
                property_name,
            )

            change_index = len(
                self._stylesheet_changes
            )

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

            changed_stylesheet_ids = list(
                dict.fromkeys(
                    self._stylesheet_changes[
                        change_index:
                    ]
                )
            )

            stylesheet_changes: list[
                dict[str, Any]
            ] = []

            for stylesheet_id in changed_stylesheet_ids:
                stylesheet = self.styles.get_stylesheet(
                    stylesheet_id
                )

                before_text = (
                    stylesheet.current_text
                    if stylesheet is not None
                    else ""
                )

                after_text = self.get_stylesheet_text(
                    stylesheet_id
                )

                self.styles.set_stylesheet_text(
                    stylesheet_id,
                    after_text,
                )

                stylesheet_changes.append(
                    {
                        "style_sheet_id": stylesheet_id,
                        "before_text": before_text,
                        "after_text": after_text,
                        "text_changed": (
                            before_text != after_text
                        ),
                        "expected_source": any(
                            source.stylesheet_id
                            == stylesheet_id
                            for source in expected_sources
                        ),
                    }
                )

            inline_change = None

            if not stylesheet_changes:
                inline_styles = (
                    self.get_inline_styles_for_node(
                        node_id
                    )
                )

                actual_property = (
                    self._find_inline_property(
                        inline_styles,
                        property_name,
                    )
                )

                previous_values = {
                    source.value
                    for source in expected_sources
                    if source.source_type
                    in {"inline", "attribute"}
                }

                actual_value = (
                    actual_property.get("value", "")
                    if actual_property is not None
                    else ""
                )

                inline_change = {
                    "property": actual_property,
                    "changed": (
                        actual_property is not None
                        and actual_value
                        not in previous_values
                    ),
                    "requested_value_found": (
                        "".join(actual_value.split()).casefold()
                        == "".join(value.split()).casefold()
                    ),
                }

            changed = (
                any(
                    change["text_changed"]
                    for change in stylesheet_changes
                )
                or bool(
                    inline_change
                    and inline_change["changed"]
                )
            )

            return {
                "backend_node_id": backend_node_id,
                "node_id": int(node_id),
                "tag_name": tag_name,
                "property_name": property_name,
                "requested_value": value,
                "changed": changed,
                "expected_sources": expected_sources,
                "stylesheet_changes": stylesheet_changes,
                "inline_change": inline_change,
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
        self._ensure_open
        assert self._cdp is not None

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

            if "exceptionDetails" in response:
                raise RuntimeError(
                    response["exceptionDetails"].get(
                        "text",
                        "Runtime.callFunctionOn falló.",
                    )
                )

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
        self._ensure_open
        assert self._page is not None

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
        self._ensure_open
        assert self._page is not None

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
        self._ensure_open
        assert self._page is not None
        assert self._cdp is not None

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
                        for document
                        in self.styles.documents.values()
                        for stylesheet
                        in document.stylesheets.values()
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
        self._ensure_open
        assert self._cdp is not None

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
        self._ensure_open
        assert self._cdp is not None

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

    def clean_inline_style_attributes(self) -> None:
        self._ensure_open
        assert self._page is not None

        try:
            self._page.evaluate(
                """
                () => {
                    const duplicateImportant =
                        /(?:!\\s*important\\s*){2,}/gi;

                    for (const element of document.querySelectorAll("[style]")) {
                        const value = element.getAttribute("style");

                        if (!value) {
                            continue;
                        }

                        const cleanValue = value.replace(
                            duplicateImportant,
                            " !important"
                        );

                        if (cleanValue !== value) {
                            element.setAttribute("style", cleanValue);
                        }
                    }
                }
                """
            )

        except Exception as exc:
            raise RuntimeError(
                "Inline style cleanup failed due to an unexpected "
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
        self._ensure_open
        assert self._cdp is not None

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
    ) -> list[tuple[float, float]]:
        """
        Obtiene las cuatro coordenadas del área de contenido del nodo.

        Devuelve una lista vacía cuando el nodo no tiene una caja visual.
        """
        self._ensure_open
        assert self._cdp is not None

        if not backend_node_id:
            return []

        try:
            response = self._cdp.send(
                "DOM.getBoxModel",
                {
                    "backendNodeId": int(backend_node_id),
                },
            )

            content = response.get("model", {}).get("content", [])

            if len(content) != 8:
                return []

            return [
                (float(x), float(y))
                for x, y in zip(
                    content[0::2],
                    content[1::2],
                )
            ]

        except Exception as exc:
            # Este error es normal para nodos sin representación visual,
            # como display: none o algunos nodos internos.
            if "Could not compute box model" in str(exc):
                return []

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
        self._ensure_open
        assert self._cdp is not None

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


    @property
    def stylesheets_meta(
        self,
    ) -> dict[str, dict[str, Any]]:
        return {
            stylesheet.stylesheet_id: {
                "frame_id": stylesheet.frame_id,
                "source_url": stylesheet.source_url,
                "origin": stylesheet.origin,
                "disabled": stylesheet.disabled,
                "is_inline": stylesheet.is_inline,
                "is_mutable": stylesheet.is_mutable,
                "is_constructed": (
                    stylesheet.is_constructed
                ),
                "loading_failed": (
                    stylesheet.loading_failed
                ),
                "owner_node": stylesheet.owner_node,
                "parent_stylesheet_id": (
                    stylesheet.parent_stylesheet_id
                ),
            }
            for document in self.styles.documents.values()
            for stylesheet
            in document.stylesheets.values()
        }


    def capture_fullpage_screenshot(
        self,
        output_path: str | Path,
    ) -> Path:
        self._ensure_open
        assert self._page is not None

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
        self._ensure_open
        assert self._cdp is not None

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
        self._ensure_open
        assert self._cdp is not None

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

            response = self._cdp.send(
                "DOM.getAttributes",
                {
                    "nodeId": int(node_id),
                },
            )

            attributes = response.get("attributes") or []

            for index in range(0, len(attributes), 2):
                name = str(attributes[index])

                if name == attribute_name:
                    return str(attributes[index + 1])

            return None

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
        self._ensure_open
        assert self._cdp is not None

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
        for source_type, style_key in (
            ("inline", "inlineStyle"),
            ("attribute", "attributesStyle"),
        ):
            style = inline_styles.get(style_key) or {}

            for css_property in (
                style.get("cssProperties") or []
            ):
                if css_property.get("disabled"):
                    continue

                if css_property.get("name") != property_name:
                    continue

                return {
                    "source_type": source_type,
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
        self._ensure_open
        assert self._cdp is not None

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
        self._ensure_open
        assert self._cdp is not None

        try:
            for document in self.styles.documents.values():
                for stylesheet in (
                    document.stylesheets.values()
                ):
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
        self._ensure_open

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
        self._ensure_open
        assert self._cdp is not None

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
        self._ensure_open
        assert self._cdp is not None

        try:
            root = self.get_full_document_node()
            node_id = root.get("nodeId")

            if not node_id:
                raise RuntimeError(
                    "El nodo raíz no contiene un nodeId válido."
                )

            response = self._cdp.send(
                "DOM.getOuterHTML",
                {
                    "nodeId": int(node_id),
                },
            )

            outer_html = str(
                response.get("outerHTML") or ""
            )

            if not outer_html.strip():
                raise RuntimeError(
                    "DOM.getOuterHTML no devolvió contenido."
                )

            return outer_html

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
        self._ensure_open
        assert self._cdp is not None

        if not selector or not selector.strip():
            return None

        try:
            if node_id is None:
                root = self.get_full_document_node()
                node_id = root.get("nodeId")

            if not node_id:
                return None

            response = self._cdp.send(
                "DOM.querySelector",
                {
                    "nodeId": int(node_id),
                    "selector": selector.strip(),
                },
            )

            matched_node_id = response.get("nodeId")

            return (
                int(matched_node_id)
                if matched_node_id
                else None
            )

        except Exception as exc:
            raise RuntimeError(
                "DOM query selector failed for "
                f"selector={selector!r}, "
                "due to an unexpected error "
                f"[{type(exc).__name__}]: {exc}"
            ) from exc

    def close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()

            if self._browser is not None:
                self._browser.close()

            if self._playwright is not None:
                self._playwright.stop()

        except Exception as exc:
            raise RuntimeError(
                "PageBuilder closing failed due to an "
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

        finally:
            self._cdp = None
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._document_root = None
            self._theme_stylesheet_id = None
            self._stylesheet_changes.clear()
            self.styles.clear()
            self._stop_server()
