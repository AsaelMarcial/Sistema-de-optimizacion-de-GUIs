import shutil
import unittest
from pathlib import Path

from flask import Flask

from engine.adapters.source_code_handler.local_asset_rewriter import (
    extract_reference_candidates,
    rewrite_reference_candidates,
)
from engine.domain.models.project_context import ProjectContext, ProjectFile, ProjectSource
from engine.pipeline.context import PipelineContext


def project_context_for(*paths: str):
    app_context = Flask(__name__).app_context()
    app_context.push()
    PipelineContext()
    from flask import g

    session_dir = g.session_dir
    before_root = g.before_root
    before_root.mkdir(parents=True, exist_ok=True)
    g.after_root.mkdir(parents=True, exist_ok=True)
    g.artifacts_root.mkdir(parents=True, exist_ok=True)

    project_files = [
        {"file_name": Path("site/index.html"), "mime_type": "text/html"}
    ]
    html_path = before_root / "site" / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text("<html></html>", encoding="utf-8")

    for path in paths:
        file_path = before_root / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"asset")
        mime_type = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".svg": "image/svg+xml",
            ".html": "text/html",
        }.get(file_path.suffix.lower(), "image/png")
        project_files.append(
            {
                "file_name": Path(path),
                "mime_type": mime_type,
            }
        )
    return app_context, ProjectContext(project_files)


class LocalAssetRewriterTest(unittest.TestCase):
    def test_extract_reference_candidates_handles_attributes_and_css_urls(self) -> None:
        self.assertEqual(
            ["icons/large.svg", "icons/small.svg"],
            sorted(
                extract_reference_candidates(
                    "icons/small.svg 1x, icons/large.svg 2x",
                    "srcset",
                )
            ),
        )
        self.assertEqual([], extract_reference_candidates("#icon", "href"))
        self.assertEqual(
            ["icons/icon.svg"],
            extract_reference_candidates(
                'linear-gradient(red, blue), url("icons/icon.svg")'
            ),
        )

    def test_rewrite_reference_candidates_preserves_srcset_descriptors(self) -> None:
        self.assertEqual(
            "assets/icon-glow.svg 1x, assets/icon-glow.svg 2x",
            rewrite_reference_candidates(
                "assets/icon.svg 1x, assets/icon.svg 2x",
                "assets/icon-glow.svg",
                "srcset",
            ),
        )

    def test_rewrite_reference_candidates_can_target_one_css_url(self) -> None:
        self.assertEqual(
            'url(assets/icon-glow.svg), url("assets/other.svg")',
            rewrite_reference_candidates(
                'url("assets/icon.svg"), url("assets/other.svg")',
                "assets/icon-glow.svg",
                old_path="assets/icon.svg",
            ),
        )

    def test_project_context_find_relative_asset_from_page_url_base(self) -> None:
        app_context, project_context = project_context_for(
            "assets/logo.png",
            "site/assets/logo.png",
        )
        try:
            project_context.page_url = "http://127.0.0.1:8000/site/index.html"

            self.assertEqual(
                Path("site/assets/logo.png"),
                project_context.project_file("assets/logo.png").path,
            )
            self.assertEqual(
                Path("assets/logo.png"),
                project_context.project_file("/assets/logo.png").path,
            )
            local_resource = project_context.add_resource(
                "http://127.0.0.1:8000/site/assets/logo.png?ver=1",
                resource_type="image",
                load_status=True,
            )
            local_file = project_context.project_file("site/assets/logo.png")

            self.assertIsInstance(local_file, ProjectFile)
            self.assertIs(local_resource, local_file.runtime_information)
            self.assertTrue(local_file.is_loaded)
        finally:
            session_dir = project_context.session_dir
            app_context.pop()
            shutil.rmtree(session_dir, ignore_errors=True)

    def test_project_source_adds_dependency_from_owner_file(self) -> None:
        app_context, project_context = project_context_for(
            "site/css/main.css",
            "site/assets/icon.svg",
        )
        try:
            css_file = project_context.project_file("site/css/main.css")
            self.assertIsNotNone(css_file)
            self.assertIsInstance(css_file, ProjectSource)

            related_file = project_context.project_file("../assets/icon", css_file)
            self.assertIsNotNone(related_file)
            reference = "../assets/icon"
            css_file.add_dependency(related_file, reference)

            self.assertEqual(Path("site/assets/icon.svg"), related_file.path)
            self.assertEqual("../assets/icon", reference)
            self.assertEqual(((reference, related_file),), tuple(css_file.resources))
        finally:
            session_dir = project_context.session_dir
            app_context.pop()
            shutil.rmtree(session_dir, ignore_errors=True)

    def test_project_context_loaded_svgs_require_successful_runtime_usage(self) -> None:
        app_context, project_context = project_context_for(
            "site/assets/icon.svg",
            "site/assets/unused.svg",
        )
        try:
            project_context.page_url = "http://127.0.0.1:8000/site/index.html"
            icon = project_context.project_file("site/assets/icon.svg")
            unused = project_context.project_file("site/assets/unused.svg")
            self.assertIsNotNone(icon)
            self.assertIsNotNone(unused)

            project_context.add_resource(
                "http://127.0.0.1:8000/site/assets/icon.svg",
                resource_type="image",
                load_status=True,
            )
            icon.add_usage(10)
            project_context.add_resource(
                "http://127.0.0.1:8000/site/assets/unused.svg",
                resource_type="image",
                load_status=True,
            )

            self.assertEqual((icon,), project_context.loaded_svgs())
        finally:
            session_dir = project_context.session_dir
            app_context.pop()
            shutil.rmtree(session_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
