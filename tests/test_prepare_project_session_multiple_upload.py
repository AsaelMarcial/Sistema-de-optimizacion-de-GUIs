from __future__ import annotations

import shutil
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from engine.adapters.file_system.file_manager import detect_type
from engine.domain.models.asset_records import AssetRecords
from engine.domain.models.session import Session
from engine.pipeline.stages import prepare_project_session


def upload(filename: str, payload: bytes) -> FileStorage:
    return FileStorage(stream=BytesIO(payload), filename=filename)


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
        session = Session()
        asset_records = AssetRecords()
        state = prepare_project_session.prepare_project_session(
            session,
            asset_records,
            [
                upload(
                    "index.html",
                    b"<html><head><link rel='stylesheet' href='style.css'></head><body></body></html>",
                ),
                upload("style.css", b"body { color: black; }"),
                upload("script.js", b"console.log('ok');"),
                upload("logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"),
            ],
            return_state=True,
        )

        try:
            self.assertTrue(state.is_completed())
            self.assertTrue((session.get_area_root("before") / "index.html").is_file())
            self.assertTrue((session.get_area_root("before") / "style.css").is_file())
            self.assertEqual(len(session.find_by_suffix("before", "html")), 1)
            self.assertEqual(
                [path.relative_to(session.get_area_root("before")).as_posix() for path in session.get_by_type(".html")],
                ["index.html"],
            )
            self.assertEqual(
                session.file_types[(session.get_area_root("before") / "index.html").resolve()],
                ".html",
            )
            self.assertIsNotNone(asset_records.find_asset("index.html"))
            self.assertIsNotNone(asset_records.find_asset("style.css"))
        finally:
            if session is not None:
                shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_rejects_zip_mixed_with_loose_files(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("index.html", "<html></html>")

        session = Session()
        asset_records = AssetRecords()
        state = prepare_project_session.prepare_project_session(
            session,
            asset_records,
            [
                upload("project.zip", buffer.getvalue()),
                upload("index.html", b"<html></html>"),
            ],
            return_state=True,
        )

        self.assertTrue(state.is_failed())

    def test_rejects_project_without_html(self) -> None:
        session = Session()
        asset_records = AssetRecords()
        state = prepare_project_session.prepare_project_session(
            session,
            asset_records,
            [upload("style.css", b"body { color: black; }")],
            return_state=True,
        )

        self.assertTrue(state.is_failed())

    def test_extracts_zip_after_validating_contents(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("site/index.html", "<html><body></body></html>")
            archive.writestr("site/css/style.css", "body { color: black; }")

        session = Session()
        asset_records = AssetRecords()
        state = prepare_project_session.prepare_project_session(
            session,
            asset_records,
            [upload("project.zip", buffer.getvalue())],
            return_state=True,
        )

        try:
            self.assertTrue(state.is_completed())
            self.assertTrue((session.get_area_root("before") / "site" / "index.html").is_file())
            self.assertTrue((session.get_area_root("before") / "site" / "css" / "style.css").is_file())
            self.assertEqual(len(session.find_by_suffix("before", "html")), 1)
            self.assertEqual(
                [path.relative_to(session.get_area_root("before")).as_posix() for path in session.get_by_type(".html")],
                ["site/index.html"],
            )
        finally:
            if session is not None:
                shutil.rmtree(session.session_dir, ignore_errors=True)


class SessionPathResolutionTests(unittest.TestCase):
    def test_find_by_full_path_resolves_clean_exact_path(self) -> None:
        session = Session()
        try:
            before_root = session.get_area_root("before")
            target = before_root / "site" / "imagenes" / "icono-de-prueba.svg"
            decoy = before_root / "other" / "icono-de-prueba.svg"
            target.parent.mkdir(parents=True, exist_ok=True)
            decoy.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<svg></svg>", encoding="utf-8")
            decoy.write_text("<svg></svg>", encoding="utf-8")
            session.file_types[target.resolve()] = ".svg"
            session.file_types[decoy.resolve()] = ".svg"

            resolved = session.find_by_full_path(
                "before",
                "site/imagenes/icono-de-prueba.svg",
            )

            self.assertEqual(resolved, Path("site/imagenes/icono-de-prueba.svg"))
            self.assertIsNone(
                session.find_by_full_path(
                    "before",
                    "missing/imagenes/icono-de-prueba.svg",
                )
            )
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_find_by_full_path_uses_video_type_for_video_suffixes(self) -> None:
        session = Session()
        try:
            before_root = session.get_area_root("before")
            thumbnail = before_root / "media" / "clip.jpeg"
            thumbnail.parent.mkdir(parents=True, exist_ok=True)
            thumbnail.write_bytes(b"jpeg")
            session.file_types[thumbnail.resolve()] = "video"

            self.assertEqual(session.get_by_type(".mp4"), [thumbnail.resolve()])
            self.assertEqual(
                session.find_by_full_path("before", "videos/clip.mp4"),
                Path("media/clip.jpeg"),
            )
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
