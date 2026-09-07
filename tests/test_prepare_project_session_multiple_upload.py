from __future__ import annotations

import shutil
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from flask import Flask, g
from werkzeug.datastructures import FileStorage

from engine.adapters.file_system.file_manager import detect_type
from engine.domain.models.project_context import ProjectContext, ProjectSource
from engine.pipeline.context import PipelineContext
from engine.pipeline.stages import prepare_project_session
from engine.pipeline.stages.static_evaluation import _register_project_file_references


def upload(filename: str, payload: bytes) -> FileStorage:
    return FileStorage(stream=BytesIO(payload), filename=filename)


def project_context_from_files(files: dict[str, tuple[bytes, str]]) -> ProjectContext:
    PipelineContext()
    session_dir = g.session_dir
    before_root = g.before_root
    before_root.mkdir(parents=True, exist_ok=True)
    g.after_root.mkdir(parents=True, exist_ok=True)
    g.artifacts_root.mkdir(parents=True, exist_ok=True)

    metadata = []
    for file_name, (content, mime_type) in files.items():
        path = Path(file_name)
        target = before_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        metadata.append({"file_name": path, "mime_type": mime_type})

    return ProjectContext(metadata)


class PrepareProjectSessionMultipleUploadTests(unittest.TestCase):
    def test_detect_type_keeps_css_suffix_for_utf8_text(self) -> None:
        with patch(
            "engine.adapters.file_system.file_manager.magic.from_buffer",
            return_value="application/octet-stream",
        ):
            self.assertEqual(
                detect_type(
                    upload(
                        "Pagina de prueba 7/css/estilos.css",
                        b"body { color: black; }",
                    )
                ),
                ".css",
            )

    def test_detect_type_rejects_binary_content_with_css_suffix(self) -> None:
        with patch(
            "engine.adapters.file_system.file_manager.magic.from_buffer",
            return_value="application/octet-stream",
        ):
            self.assertEqual(
                detect_type(
                    upload(
                        "Pagina de prueba 7/css/estilos.css",
                        b"\x89PNG\r\n\x1a\n\x00\x00",
                    )
                ),
                "",
            )

    def test_materializes_multiple_allowed_files(self) -> None:
        app = Flask(__name__)
        with app.app_context():
            try:
                with PipelineContext() as context:
                    g.upload = [
                        upload(
                            "index.html",
                            b"<html><head><link rel='stylesheet' href='style.css'></head><body></body></html>",
                        ),
                        upload("style.css", b"body { color: black; }"),
                        upload("script.js", b"console.log('ok');"),
                        upload(
                            "logo.svg",
                            b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
                        ),
                    ]
                    state = prepare_project_session.prepare_project_session(
                        return_state=True,
                    )

                self.assertTrue(state.is_completed())
                project_context = context.project_context
                self.assertIsInstance(project_context, ProjectContext)
                self.assertTrue((project_context.root / "index.html").is_file())
                self.assertTrue((project_context.root / "style.css").is_file())
                self.assertEqual(len(tuple(project_context.root.rglob("*.html"))), 1)
                self.assertEqual(
                    [
                        path.relative_to(project_context.root).as_posix()
                        for path in project_context.get_by_type(".html")
                    ],
                    ["index.html"],
                )
                self.assertIsNotNone(
                    context.project_context.project_file("index.html")
                )
                self.assertIsNotNone(
                    context.project_context.project_file("style.css")
                )
            finally:
                if context.project_context is not None:
                    shutil.rmtree(
                        context.project_context.session_dir,
                        ignore_errors=True,
                    )

    def test_rejects_zip_mixed_with_loose_files(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("index.html", "<html></html>")

        app = Flask(__name__)
        with app.app_context():
            with PipelineContext():
                g.upload = [
                    upload("project.zip", buffer.getvalue()),
                    upload("index.html", b"<html></html>"),
                ]
                state = prepare_project_session.prepare_project_session(
                    return_state=True,
                )

        self.assertTrue(state.is_failed())

    def test_rejects_project_without_html(self) -> None:
        app = Flask(__name__)
        with app.app_context():
            with PipelineContext():
                g.upload = [upload("style.css", b"body { color: black; }")]
                state = prepare_project_session.prepare_project_session(
                    return_state=True,
                )

        self.assertTrue(state.is_failed())

    def test_extracts_zip_after_validating_contents(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("site/index.html", "<html><body></body></html>")
            archive.writestr("site/css/style.css", "body { color: black; }")

        app = Flask(__name__)
        with app.app_context():
            try:
                with PipelineContext() as context:
                    g.upload = [upload("project.zip", buffer.getvalue())]
                    state = prepare_project_session.prepare_project_session(
                        return_state=True,
                    )

                self.assertTrue(state.is_completed())
                project_context = context.project_context
                self.assertIsInstance(project_context, ProjectContext)
                self.assertTrue(
                    (project_context.root / "site" / "index.html").is_file()
                )
                self.assertTrue(
                    (project_context.root / "site" / "css" / "style.css").is_file()
                )
                stylesheet = project_context.project_file("site/css/style.css")
                self.assertIsInstance(stylesheet, ProjectSource)
                self.assertEqual(stylesheet.mime_type, "text/css")
                self.assertEqual(len(tuple(project_context.root.rglob("*.html"))), 1)
                self.assertEqual(
                    [
                        path.relative_to(project_context.root).as_posix()
                        for path in project_context.get_by_type(".html")
                    ],
                    ["site/index.html"],
                )
            finally:
                if context.project_context is not None:
                    shutil.rmtree(
                        context.project_context.session_dir,
                        ignore_errors=True,
                    )

    def test_accepts_zip_when_magic_reports_octet_stream(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("site/index.html", "<html><body></body></html>")

        with patch("engine.utilities.files.magic.Magic") as magic_mock:
            detector = magic_mock.return_value
            detector.from_buffer.side_effect = [
                "application/octet-stream",
                "text/plain",
            ]

            validated_files = prepare_project_session.file_validator(
                [upload("project.zip", buffer.getvalue())]
            )

        self.assertEqual(
            validated_files,
            [
                {
                    "file_name": Path("site/index.html"),
                    "content": b"<html><body></body></html>",
                    "mime_type": "text/html",
                }
            ],
        )


class ProjectContextPathResolutionTests(unittest.TestCase):
    def test_project_file_resolves_clean_exact_path(self) -> None:
        app = Flask(__name__)
        with app.app_context():
            project_context = project_context_from_files(
                {
                    "site/index.html": (b"<html></html>", "text/html"),
                    "site/imagenes/icono-de-prueba.svg": (
                        b"<svg></svg>",
                        "image/svg+xml",
                    ),
                    "other/icono-de-prueba.svg": (b"<svg></svg>", "image/svg+xml"),
                }
            )
            resolved = project_context.project_file(
                "site/imagenes/icono-de-prueba.svg",
            )

            self.assertIsNotNone(resolved)
            self.assertEqual(resolved.path, Path("site/imagenes/icono-de-prueba.svg"))
            self.assertIsNone(
                project_context.project_file(
                    "missing/imagenes/icono-de-prueba.svg",
                )
            )
            shutil.rmtree(project_context.session_dir, ignore_errors=True)

    def test_static_evaluation_follows_css_imports(self) -> None:
        app = Flask(__name__)
        with app.app_context():
            project_context = project_context_from_files(
                {
                    "site/index.html": (
                        b"<html><head><link rel='stylesheet' href='css/style.css'></head></html>",
                        "text/html",
                    ),
                    "site/css/style.css": (
                        b"@import 'base.css'; .card { background: url('../img/bg.svg'); }",
                        "text/css",
                    ),
                    "site/css/base.css": (
                        b"body { color: black; }",
                        "text/css",
                    ),
                    "site/img/bg.svg": (
                        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
                        "image/svg+xml",
                    ),
                }
            )

            try:
                evaluated_count = _register_project_file_references()
                stylesheet = project_context.project_file("site/css/style.css")

                self.assertEqual(evaluated_count, 3)
                self.assertIsInstance(stylesheet, ProjectSource)
                self.assertEqual(
                    {
                        related.path.as_posix()
                        for _reference, related in stylesheet.resources
                    },
                    {
                        "site/css/base.css",
                        "site/img/bg.svg",
                    },
                )
            finally:
                shutil.rmtree(project_context.session_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
