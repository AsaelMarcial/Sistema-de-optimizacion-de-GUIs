from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Self
from urllib.parse import quote


class _StaticRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class StaticServer:
    def __init__(self, root: str | Path) -> None:
        try:
            self.root = Path(root).resolve(strict=True)
            self.host = "127.0.0.1"
            self.server: ThreadingHTTPServer | None = None
            self.thread: Thread | None = None

        except Exception as e:
            error_nombre = type(e).__name__
            error_desc = str(e)
            raise RuntimeError(
                f"[StaticServer.__init__] Ocurrió un error de tipo [{error_nombre}]. "
                f"Descripción: {error_desc}"
            ) from e

    @property
    def origin(self) -> str:
        try:
            if not self.server:
                raise RuntimeError("El servidor no ha sido iniciado mediante __enter__.")
            port = self.server.server_port
            return f"http://{self.host}:{port}"
        except Exception as e:
            error_nombre = type(e).__name__
            error_desc = str(e)
            raise RuntimeError(
                f"[StaticServer.origin] No se pudo obtener la URL base. "
                f"Error: [{error_nombre}] - {error_desc}"
            ) from e

    def __enter__(self) -> Self:
        """Inicia el servidor y el hilo secundario controlando cualquier fallo de red."""
        try:
            if self.server:
                return self

            handler = partial(_StaticRequestHandler, directory=str(self.root))
            self.server = ThreadingHTTPServer((self.host, 0), handler)

            self.thread = Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            return self

        except Exception as e:
            error_nombre = type(e).__name__
            error_desc = str(e)
            self.__exit__(None, None, None)
            raise RuntimeError(
                f"[StaticServer.__enter__] Falló el arranque del servidor en {self.host}. "
                f"Error: [{error_nombre}] - {error_desc}"
            ) from e

    def url_for(self, path: str | Path) -> str:
        """Genera la URL resolviendo y validando que el archivo esté dentro de la raíz."""
        try:
            path_absoluto = Path(path).resolve()
            relative = path_absoluto.relative_to(self.root)
            return f"{self.origin}/{quote(relative.as_posix().lstrip('/'), safe='/')}"

        except Exception as e:
            error_nombre = type(e).__name__
            error_desc = str(e)
            raise RuntimeError(
                f"[StaticServer.url_for] No se pudo generar la URL para '{path}'. "
                f"Error: [{error_nombre}] - {error_desc}"
            ) from e

    def __exit__(self, exc_type, exc, traceback) -> bool:
        """Apaga el servidor sin ocultar excepciones del bloque with."""
        close_errors: list[str] = []

        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as close_exc:
                close_errors.append(
                    f"server [{type(close_exc).__name__}]: {close_exc}"
                )
            finally:
                self.server = None

        if self.thread and self.thread.is_alive():
            try:
                self.thread.join(timeout=1.0)
            except Exception as close_exc:
                close_errors.append(
                    f"thread [{type(close_exc).__name__}]: {close_exc}"
                )
            finally:
                self.thread = None

        if close_errors and exc_type is None:
            raise RuntimeError(
                "StaticServer close failed: " + "; ".join(close_errors)
            )

        return False
