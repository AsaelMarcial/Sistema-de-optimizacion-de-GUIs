from __future__ import annotations

import shutil
import unittest
import zipfile
from io import BytesIO

from werkzeug.datastructures import FileStorage

from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.context import PipelineContext
from engine.pipeline.stages import prepare_project_session


def upload(filename: str, payload: bytes) -> FileStorage:
    return FileStorage(stream=BytesIO(payload), filename=filename)


class PrepareProjectSessionMultipleUploadTests(unittest.TestCase):
    def test_materializes_multiple_allowed_files(self) -> None:
        context = prepare_project_session.run_stage(
            PipelineContext(),
            [
                upload(
                    "index.html",
                    b"<html><head><link rel='stylesheet' href='style.css'></head><body></body></html>",
                ),
                upload("style.css", b"body { color: black; }"),
                upload("script.js", b"console.log('ok');"),
                upload("logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"),
            ],
        )

        try:
            self.assertIsNone(context.error)
            session = context.get(K.SESSION)
            self.assertTrue((session.get_area_root("before") / "index.html").is_file())
            self.assertTrue((session.get_area_root("before") / "style.css").is_file())
            self.assertEqual(len(session.find_by_suffix("before", "html")), 1)
        finally:
            session = context.get(K.SESSION)
            if session is not None:
                shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_rejects_zip_mixed_with_loose_files(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("index.html", "<html></html>")

        context = prepare_project_session.run_stage(
            PipelineContext(),
            [
                upload("project.zip", buffer.getvalue()),
                upload("index.html", b"<html></html>"),
            ],
        )

        self.assertEqual(context.error, "Operation aborted. Mixing a ZIP file and loose files is forbidden.")

    def test_rejects_project_without_html(self) -> None:
        context = prepare_project_session.run_stage(
            PipelineContext(),
            [upload("style.css", b"body { color: black; }")],
        )

        self.assertEqual(context.error, "Operation aborted. It has to be one HTML file.")

    def test_extracts_zip_after_validating_contents(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("site/index.html", "<html><body></body></html>")
            archive.writestr("site/css/style.css", "body { color: black; }")

        context = prepare_project_session.run_stage(
            PipelineContext(),
            [upload("project.zip", buffer.getvalue())],
        )

        try:
            self.assertIsNone(context.error)
            session = context.get(K.SESSION)
            self.assertTrue((session.get_area_root("before") / "site" / "index.html").is_file())
            self.assertTrue((session.get_area_root("before") / "site" / "css" / "style.css").is_file())
            self.assertEqual(len(session.find_by_suffix("before", "html")), 1)
        finally:
            session = context.get(K.SESSION)
            if session is not None:
                shutil.rmtree(session.session_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
