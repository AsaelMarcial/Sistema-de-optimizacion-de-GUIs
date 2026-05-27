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

from engine.adapters.file_system.file_manager import ensure_parent_dir


class _ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class PageBuilder:
    def __init__(
        self,
        html_path: str | Path,
        *,
        port: int = 8000,
        options: Any | None = None,
    ) -> None:
        self.html_path = Path(html_path).resolve()
        if not self.html_path.is_file():
            raise FileNotFoundError(f"HTML no encontrado: {self.html_path}")

        self.options = options
        self.base_path = self.html_path.parent
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._cdp: CDPSession | None = None
        self._server: _ReusableTCPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._port = int(port)

        try:
            self._init_playwright()
            self.load_page(self.html_path)
        except Exception:
            self.close()
            raise

    @classmethod
    def new_from_file(
        cls,
        html_path: str | Path,
        *,
        options: Any | None = None,
        existing: "PageBuilder | None" = None,
    ) -> "PageBuilder":
        if existing is not None and existing.is_open:
            raise ValueError("Ya existe una instancia activa de PageBuilder.")
        return cls(html_path=html_path, options=options)

    @property
    def is_open(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    def _init_playwright(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            viewport={"width": 1366, "height": 768},
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(30000)
        self._page.set_default_navigation_timeout(30000)
        self._cdp = self._context.new_cdp_session(self._page)
        self._cdp.send("DOM.enable")
        self._cdp.send("CSS.enable")

    def _ensure_open(self) -> None:
        if not self.is_open or self._page is None or self._cdp is None:
            raise RuntimeError("PageBuilder esta cerrado.")

    def load_page(self, html_path: str | Path) -> None:
        self._ensure_open()
        target = Path(html_path).resolve()
        if not target.is_file():
            raise FileNotFoundError(f"HTML no encontrado: {target}")

        self.html_path = target
        self.base_path = target.parent
        self._restart_server(target.parent)
        assert self._page is not None
        self._page.goto(
            f"http://127.0.0.1:{self._port}/{target.name}",
            wait_until="domcontentloaded",
        )
        self.wait_for_render_ready()

    def wait_for_render_ready(self) -> None:
        self._ensure_open()
        assert self._page is not None
        try:
            self._page.wait_for_load_state("load")
            self._page.wait_for_function("() => document.readyState === 'complete'")
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
            raise RuntimeError(f"No se pudo capturar DOMSnapshot: {exc}") from exc

    def get_full_document_node(self) -> dict[str, Any]:
        self._ensure_open()
        assert self._cdp is not None
        try:
            response = self._cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
        except PlaywrightError as exc:
            raise RuntimeError(f"No se pudo obtener DOM.getDocument: {exc}") from exc
        return dict(response.get("root") or {})

    def capture_full_page_screenshot(self, *, output_path: str | Path) -> str | None:
        self._ensure_open()
        if bool(getattr(self.options, "capture_screenshot", True)) is False:
            return None
        assert self._page is not None
        target = Path(output_path).resolve()
        ensure_parent_dir(target)
        self._page.screenshot(path=str(target), full_page=True, caret="initial")
        return str(target)

    def close(self) -> None:
        errors: list[str] = []
        for label, closer in (
            ("CDP detach", lambda: self._cdp.detach() if self._cdp else None),
            ("Context close", lambda: self._context.close() if self._context else None),
            ("Browser close", lambda: self._browser.close() if self._browser else None),
            ("Playwright stop", lambda: self._playwright.stop() if self._playwright else None),
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

        try:
            self._stop_server()
        except Exception as exc:
            errors.append(f"Server close: {exc}")

        if errors:
            raise RuntimeError("Errores al cerrar PageBuilder: " + " | ".join(errors))

    def _restart_server(self, directory: Path) -> None:
        self._stop_server()
        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler,
            directory=str(directory),
        )
        while self._port < 9000:
            try:
                self._server = _ReusableTCPServer(("127.0.0.1", self._port), handler)
                self._server_thread = threading.Thread(
                    target=self._server.serve_forever,
                    daemon=True,
                )
                self._server_thread.start()
                return
            except OSError:
                self._port += 1
        raise RuntimeError("No se encontro un puerto disponible para servir el HTML.")

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
