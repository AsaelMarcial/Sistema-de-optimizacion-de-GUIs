from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path
from typing import Any

from playwright.sync_api import (
    Browser,
    BrowserContext,
    CDPSession,
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


class _ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class _QuietStaticHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return


class PageBuilder:
    def __init__(
        self,
        *,
        port: int = 8000,
    ) -> None:
        self.html_path: Path | None = None
        self.base_path: Path | None = None
        self._desktop_chrome: any = None
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._cdp: CDPSession | None = None
        self._server: _ReusableTCPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._port = int(port)
        self._stylesheets_meta: dict[str, dict[str, Any]] = {}
        self._document_loaded = False

        try:
            self._init_playwright()
        except Exception:
            self.close()
            raise

    @property
    def is_open(self) -> bool:
        return (
            self._browser is not None
            and self._browser.is_connected()
            and self._page is not None
            and not self._page.is_closed()
            and self._cdp is not None
        )

    def _init_playwright(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._desktop_chrome = self._playwright.devices["Desktop Chrome"]
        self._context = self._browser.new_context(**self._desktop_chrome)
        self._page = self._context.new_page()

        self._cdp = self._context.new_cdp_session(self._page)
        self._cdp.send("DOM.enable")
        self._cdp.send("CSS.enable")
        self._cdp.on("CSS.styleSheetAdded", self._on_stylesheet_added)

    def _on_stylesheet_added(self, event: dict[str, Any]) -> None:
        header = dict(event.get("header") or {})
        stylesheet_id = str(header.get("styleSheetId") or "").strip()
        if not stylesheet_id:
            return
        self._stylesheets_meta[stylesheet_id] = {
            "is_inline": bool(header.get("isInline", False)),
            "source_url": str(header.get("sourceURL") or ""),
        }

    def _ensure_open(self) -> None:
        if not self.is_open:
            raise RuntimeError("PageBuilder esta cerrado.")

    def load_page(self, html_path: str | Path) -> None:
        self._ensure_open()
        target = Path(html_path).resolve()
        if not target.is_file():
            raise FileNotFoundError(f"HTML no encontrado: {target}")

        self.html_path = target
        self.base_path = target.parent
        self._document_loaded = False
        self._restart_server(target.parent)
        assert self._page is not None
        self._page.goto(
            f"http://127.0.0.1:{self._port}/{target.name}",
            wait_until="networkidle",
        )
        self.wait_for_render_ready()

    def wait_for_render_ready(self) -> None:
        self._ensure_open()
        assert self._page is not None
        try:
            self._page.wait_for_load_state("load")
            self._page.wait_for_function(
                "() => document.readyState === 'complete'")
            self._page.wait_for_function(
                """
                () => !document.fonts || !document.fonts.ready
                  || document.fonts.ready.then(() => true).catch(() => true)
                """
            )
        except PlaywrightTimeoutError:
            return

    def extract_raw_snapshot(self, whitelist_styles: list[str]) -> dict[str, Any]:
        self._ensure_open()
        assert self._cdp is not None
        try:
            return self._cdp.send(
                "DOMSnapshot.captureSnapshot",
                {"computedStyles": list(whitelist_styles)},
            )
        except PlaywrightError as exc:
            raise RuntimeError(
                f"No se pudo capturar DOMSnapshot: {exc}") from exc

    def get_full_document_node(self) -> dict[str, Any]:
        self._ensure_open()
        assert self._cdp is not None
        try:
            response = self._cdp.send(
                "DOM.getDocument", {"depth": -1, "pierce": True})
        except PlaywrightError as exc:
            raise RuntimeError(
                f"No se pudo obtener DOM.getDocument: {exc}") from exc
        self._document_loaded = True
        return dict(response.get("root") or {})

    def resolve_backend_node_id(self, backend_node_id: int) -> int | None:
        self._ensure_open()
        assert self._cdp is not None
        if not backend_node_id:
            return None
        try:
            if not self._document_loaded:
                self.get_full_document_node()
            response = self._cdp.send(
                "DOM.describeNode",
                {"backendNodeId": int(backend_node_id)},
            )
            return response.get("node")
        except (PlaywrightError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"No se pudo resolver el backendNodeId: {exc}"
            ) from exc

    def set_effective_value(self, node_id: int, property_name: str, value: str) -> str | None:
        self._ensure_open()
        assert self._cdp is not None
        if not node_id:
            return None
        try:
            if not self._document_loaded:
                self.get_full_document_node()
            self._cdp.send(
                "CSS.setEffectivePropertyValueForNode",
                {"nodeId": int(node_id), "propertyName": property_name, "value": value},
            )
            return self._current_property_value(int(node_id), property_name)
        except (PlaywrightError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"No se pudo cambiar el valor: {exc}"
            ) from exc

    def clean_property_value(self, node_id: int, property_name: str) -> str | None:
        self._ensure_open()
        assert self._cdp is not None
        if not node_id:
            return None
        try:
            if not self._document_loaded:
                self.get_full_document_node()
            self._cdp.send(
                "CSS.setEffectivePropertyValueForNode",
                {"nodeId": int(node_id), "propertyName": property_name, "value": ""},
            )
            return self._current_property_value(int(node_id), property_name)
        except (PlaywrightError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"No se pudo cambiar el valor: {exc}"
            ) from exc

    def _current_property_value(self, node_id: int, property_name: str) -> str | None:
        assert self._cdp is not None
        try:
            resolved = self._cdp.send(
                "DOM.resolveNode",
                {"nodeId": int(node_id)},
            )
            object_id = resolved.get("object", {}).get("objectId")
            if not object_id:
                return None
            response = self._cdp.send(
                "Runtime.callFunctionOn",
                {
                    "objectId": object_id,
                    "functionDeclaration": """
                        function(prop) {
                            return this[prop]
                                || window.getComputedStyle(this).getPropertyValue(prop);
                        }
                    """,
                    "arguments": [{"value": property_name}],
                    "returnByValue": True,
                },
            )
            return response.get("result", {}).get("value")
        except (PlaywrightError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"No se pudo cambiar el valor: {exc}"
            ) from exc

    def set_color_scheme(self) -> bool:
        self._ensure_open()
        assert self._page is not None
        try:
            content = self._page.evaluate("""
                () => {
                    let meta = document.querySelector('meta[name="color-scheme"]');
                    if (meta && meta.content == "dark"){
                        return meta.content;
                    }
                    if (!meta) {
                        meta = document.createElement('meta');
                        meta.name = 'color-scheme';
                        document.head.appendChild(meta);
                    }
                    meta.content = 'dark';
                    return meta.content;
                }
            """)
            
            return content == "dark"
        except PlaywrightError as exc:
            raise RuntimeError(
                f"No se pudo inyectar color_scheme: {exc}"
            ) from exc

    def set_data_theme(self) -> bool:
        self._ensure_open()
        assert self._page is not None
        try:
            theme = self._page.evaluate("""
                () => new Promise((resolve) => {
                    const root = document.documentElement;
                    let settled = false;
                    const finish = () => {
                        if (settled) return;
                        settled = true;
                        resolve(root.getAttribute('data-theme'));
                    };

                    if (root.getAttribute('data-theme') !== 'glow') {
                        root.setAttribute('data-theme', 'glow');
                    }
                    requestAnimationFrame(() => {
                        requestAnimationFrame(finish);
                    });
                    window.setTimeout(finish, 1000);
                })
            """)
            return theme == "glow"
        except PlaywrightError as exc:
            raise RuntimeError(
                f"No se pudo inyectar data-theme: {exc}"
            ) from exc

    def set_theme_link(self) -> bool:
        self._ensure_open()
        assert self._page is not None
        try:
            href = self._page.evaluate("""
                () => new Promise((resolve) => {
                    const href = 'glow.css';
                    let link = Array
                        .from(document.querySelectorAll('link[rel~="stylesheet"]'))
                        .find((candidate) => {
                            const rawHref = candidate.getAttribute('href') || '';
                            return candidate.dataset.glowTheme === 'true'
                                || rawHref === href
                                || rawHref.endsWith('/glow.css')
                                || candidate.href.endsWith('/glow.css');
                        });
                    if (!link) {
                        link = document.createElement('link');
                    }

                    let settled = false;
                    const finish = () => {
                        if (settled) return;
                        settled = true;
                        resolve(link.getAttribute('href'));
                    };

                    link.rel = 'stylesheet';
                    link.dataset.glowTheme = 'true';
                    link.addEventListener('load', finish, { once: true });
                    link.addEventListener('error', finish, { once: true });
                    link.href = href;
                    document.head.appendChild(link);
                    if (link.sheet) {
                        finish();
                    }
                    window.setTimeout(finish, 1000);
                })
            """)
            return href == "glow.css"
        except PlaywrightError as exc:
            raise RuntimeError(
                f"No se pudo inyectar el link del theme: {exc}"
            ) from exc

    def get_background_colors(self, node_id: int) -> dict[str, Any]:
        """Retrieve the computed background colors and text metrics for a node.

        Args:
            node_id: The active protocol identifier for the target DOM node.

        Returns:
            A dictionary containing:
                - "background_colors": List of colors found (e.g., ["#ffffff"]).
                - "font_size": Computed font size string or empty if text absent.
                - "font_weight": Computed font weight string or empty if text absent.
        """
        self._ensure_open()
        assert self._cdp is not None

        try:
            # Execute the native Chrome DevTools Protocol CSS command
            response = self._cdp.send(
                "CSS.getBackgroundColors",
                {"nodeId": int(node_id)},
            )

            # Deconstruct the native payload into a clean Python dictionary
            return {
                "background_colors": response.get("backgroundColors", []),
                "font_size": response.get("computedFontSize", ""),
                "font_weight": response.get("computedFontWeight", ""),
            }

        except PlaywrightError as exc:
            raise RuntimeError(
                f"No se pudo obtener CSS.getBackgroundColors: {exc}"
            ) from exc

    def get_box_model(self, backend_node_id: int) -> list[tuple[float, float]]:
        """Retrieve content quad coordinates for a specific backend node ID.

        Returns:
            A list of four coordinate tuples [(x1, y1), ..., (x4, y4)]
            or an empty list if the element lacks visual rendering.
        """
        self._ensure_open()
        assert self._cdp is not None

        try:
            response = self._cdp.send(
                "DOM.getBoxModel",
                {"backendNodeId": int(backend_node_id)}
            )

            # Desempaquetado limpio y seguro sin encadenar .get() excesivos
            flat_quad = response.get("model", {}).get("content")
            if not flat_quad or len(flat_quad) != 8:
                return []

            # Técnica de empaquetado simétrico ultra rápida:
            # Crea tuplas agrupando elementos nones con pares de forma simultánea
            return [
                (float(x), float(y))
                for x, y in zip(flat_quad[0::2], flat_quad[1::2])
            ]

        except PlaywrightError as exc:
            raise RuntimeError(
                f"No se pudo obtener DOM.getBoxModel: {exc}"
            ) from exc

    def get_computed_styles_for_node(self, node_id: int) -> dict[str, str]:
        """Retrieve all computed CSS styles for a specific node ID.

        Args:
            node_id: The persistent unique identifier of the DOM node.

        Returns:
            A flat dictionary where keys are CSS property names and values are
            their computed values (e.g., {"display": "block", "color": "rgb(0,0,0)"}).
        """
        self._ensure_open()
        assert self._cdp is not None

        try:
            # Note: This command belongs strictly to the "CSS" domain in CDP
            response = self._cdp.send(
                "CSS.getComputedStyleForNode",
                {"nodeId": int(node_id)},
            )

            # The protocol returns: {"computedStyle": [{"name": "...", "value": "..."}]}
            computed_style_list = response.get("computedStyle", [])

            # Transform the native CDP array into a clean Python dictionary
            style_dictionary = {
                prop["name"]: prop["value"] for prop in computed_style_list
            }

            return style_dictionary

        except PlaywrightError as exc:
            raise RuntimeError(
                f"No se pudo obtener CSS.getComputedStyleForNode: {exc}"
            ) from exc

    @property
    def stylesheets_meta(self) -> dict[str, dict[str, Any]]:
        return {key: dict(value) for key, value in self._stylesheets_meta.items()}

    def capture_fullpage_screenshot(self, output_path: str | Path) -> Path:
        """Captura una pantalla completa de la página sin animaciones ni cursor.

        Args:
            output_path: Ruta del archivo donde se guardará la imagen.
            **kwargs: Parámetros adicionales opcionales para Playwright.

        Returns:
            Un objeto Path con la ubicación del archivo guardado.
        """
        # Validar que la conexión y el cliente CDP estén activos
        self._ensure_open()
        assert self._cdp is not None

        # Convertir la ruta a un objeto Path para mayor compatibilidad de SO
        path_obj = Path(output_path)

        try:
            # Ejecutar la captura con las configuraciones visuales limpias
            self._page.screenshot(
                path=path_obj,
                full_page=True,
                animations="disabled",
                caret="initial",
            )
            return path_obj

        except PlaywrightError as exc:
            # Propagar el fallo con un mensaje contextualizado
            raise RuntimeError(
                f"Error al capturar pantalla en {path_obj}: {exc}"
            ) from exc

    def close(self) -> None:
        errors: list[str] = []
        for label, closer in (
            ("CDP detach", lambda: self._cdp.detach() if self._cdp else None),
            ("Context close", lambda: self._context.close()
             if self._context else None),
            ("Browser close", lambda: self._browser.close()
             if self._browser else None),
            ("Playwright stop", lambda: self._playwright.stop()
             if self._playwright else None),
        ):
            try:
                closer()
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        self._cdp = None
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._document_loaded = False

        try:
            self._stop_server()
        except Exception as exc:
            errors.append(f"Server close: {exc}")

        if errors:
            raise RuntimeError(
                "Errores al cerrar PageBuilder: " + " | ".join(errors))

    def _restart_server(self, directory: Path) -> None:
        self._stop_server()
        handler = functools.partial(
            _QuietStaticHandler,
            directory=str(directory),
        )
        while self._port < 9000:
            try:
                self._server = _ReusableTCPServer(
                    ("127.0.0.1", self._port), handler)
                self._server_thread = threading.Thread(
                    target=self._server.serve_forever,
                    daemon=True,
                )
                self._server_thread.start()
                return
            except OSError:
                self._port += 1
        raise RuntimeError(
            "No se encontro un puerto disponible para servir el HTML.")

    def _stop_server(self) -> None:
        if self._server is None:
            return
        server = self._server
        self._server = None
        try:
            server.shutdown()
        finally:
            server.server_close()
            self._server_thread = None
