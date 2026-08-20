from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
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
                raise RuntimeError("El servidor no ha sido iniciado mediante el método open().")
            host, port = self.server.server_address
            return f"http://[{host}]:{port}" if ":" in host else f"http://{host}:{port}"
        except Exception as e:
            error_nombre = type(e).__name__
            error_desc = str(e)
            raise RuntimeError(
                f"[StaticServer.origin] No se pudo obtener la URL base. "
                f"Error: [{error_nombre}] - {error_desc}"
            ) from e

    def open(self) -> "StaticServer":
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
            self.close()
            raise RuntimeError(
                f"[StaticServer.open] Falló el arranque del servidor en {self.host}. "
                f"Error: [{error_nombre}] - {error_desc}"
            ) from e

    def url_for(self, path: str | Path) -> str:
        """Genera la URL resolviendo y validando que el archivo esté dentro de la raíz."""
        try:
            path_absoluto = Path(path).resolve()
            relative = path_absoluto.relative_to(self.root)
            return f"{self.origin}/{quote(relative.as_posix().lstrip('/'), safe='/')}"

        except ValueError as e:
            raise ValueError(
                f"[StaticServer.url_for] Violación de seguridad. El archivo '{path}' "
                f"está fuera de la raíz '{self.root}'. Error: [ValueError] - {str(e)}"
            ) from e
        except Exception as e:
            error_nombre = type(e).__name__
            error_desc = str(e)
            raise RuntimeError(
                f"[StaticServer.url_for] No se pudo generar la URL para '{path}'. "
                f"Error: [{error_nombre}] - {error_desc}"
            ) from e

    def close(self) -> None:
        """Apaga el servidor y el hilo garantizando que las variables pasen a None."""
        server = self.server
        thread = self.thread

        self.server = None
        self.thread = None

        if server:
            server.shutdown()
            server.server_close()

        if thread and thread.is_alive():
            thread.join(timeout=1.0)
