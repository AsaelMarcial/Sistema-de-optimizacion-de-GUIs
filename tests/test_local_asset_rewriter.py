import unittest
from pathlib import Path
import shutil

from engine.adapters.source_code_handler.local_asset_rewriter import (
    _rewrite_css_urls,
    rewrite_local_asset_references,
)
from engine.domain.models.asset_records import AssetRecords, LocalAsset
from engine.domain.models.session import Session


def register_local_assets(session: Session, asset_records: AssetRecords) -> None:
    before_root = session.get_area_root("before").resolve()
    asset_records.root = before_root
    session.update_area_root_paths("before")
    session.file_types = {
        path.resolve(): path.suffix.lower() or "unknown"
        for path in before_root.rglob("*")
        if path.is_file()
    }
    for path, file_type in session.file_types.items():
        asset_records.add_local_asset(
            path.relative_to(before_root),
            file_type=file_type,
            origin="local",
        )


class LocalAssetRewriterTest(unittest.TestCase):
    def test_rewrites_path_attrs_without_losing_html_document(self) -> None:
        session = Session()
        asset_records = AssetRecords()
        try:
            before_root = session.get_area_root("before")
            assets_dir = before_root / "assets"
            assets_dir.mkdir(parents=True)
            (assets_dir / "logo.png").write_bytes(b"logo")
            (assets_dir / "small.png").write_bytes(b"small")
            (assets_dir / "large.png").write_bytes(b"large")

            html_path = before_root / "index.html"
            html_path.write_text(
                """
                <html>
                  <head><title>Keep me</title></head>
                  <body>
                    <p>Body text</p>
                    <img src="missing/logo.png?ver=1#hero">
                    <img alt="No path attr">
                    <source srcset="missing/small.png 1x, missing/large.png 2x">
                  </body>
                </html>
                """,
                encoding="utf-8",
            )
            register_local_assets(session, asset_records)

            result = rewrite_local_asset_references(
                html_path,
                session,
                asset_records,
            )
            rewritten_html = html_path.read_text(encoding="utf-8")

            self.assertEqual(
                [
                    "assets/logo.png?ver=1#hero",
                    "assets/small.png",
                    "assets/large.png",
                ],
                result,
            )
            self.assertIn("<title>Keep me</title>", rewritten_html)
            self.assertIn("<p>Body text</p>", rewritten_html)
            self.assertIn(
                'src="assets/logo.png?ver=1#hero"',
                rewritten_html,
            )
            self.assertIn(
                'srcset="assets/small.png 1x, assets/large.png 2x"',
                rewritten_html,
            )
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_rewrites_css_urls_with_tinycss2_tokens(self) -> None:
        session = Session()
        asset_records = AssetRecords()
        try:
            before_root = session.get_area_root("before")
            assets_dir = before_root / "assets"
            assets_dir.mkdir(parents=True)
            (assets_dir / "logo.png").write_bytes(b"logo")
            (assets_dir / "small.png").write_bytes(b"small")
            (assets_dir / "large.png").write_bytes(b"large")
            register_local_assets(session, asset_records)

            rewritten_css = _rewrite_css_urls(
                (
                    "background: url(missing/logo.png), "
                    'image-set(url("missing/small.png") 1x, '
                    "url(missing/large.png) 2x);"
                ),
                session,
                asset_records,
                before_root,
                before_root,
            )

            self.assertIn("url(assets/logo.png)", rewritten_css)
            self.assertIn("url(assets/small.png)", rewritten_css)
            self.assertIn("url(assets/large.png)", rewritten_css)
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_rewrites_any_attribute_or_style_value_with_local_path(self) -> None:
        session = Session()
        asset_records = AssetRecords()
        try:
            before_root = session.get_area_root("before")
            assets_dir = before_root / "assets"
            assets_dir.mkdir(parents=True)
            (assets_dir / "logo.png").write_bytes(b"logo")
            (assets_dir / "hero.png").write_bytes(b"hero")
            (assets_dir / "panel.png").write_bytes(b"panel")

            html_path = before_root / "index.html"
            html_path.write_text(
                """
                <html>
                  <head>
                    <style>.hero { background: url(missing/hero.png); }</style>
                  </head>
                  <body>
                    <div data-icon="missing/logo.png"></div>
                    <section style='background-image: url("missing/panel.png")'></section>
                  </body>
                </html>
                """,
                encoding="utf-8",
            )
            register_local_assets(session, asset_records)

            result = rewrite_local_asset_references(html_path, session, asset_records)
            rewritten_html = html_path.read_text(encoding="utf-8")

            self.assertEqual(
                [
                    "assets/hero.png",
                    "assets/logo.png",
                    "assets/panel.png",
                ],
                result,
            )
            self.assertIn('data-icon="assets/logo.png"', rewritten_html)
            self.assertIn("url(assets/hero.png)", rewritten_html)
            self.assertIn("url(assets/panel.png)", rewritten_html)
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_keeps_existing_relative_path_inside_nested_project(self) -> None:
        session = Session()
        asset_records = AssetRecords()
        try:
            before_root = session.get_area_root("before")
            project_dir = before_root / "Pagina de prueba 7"
            css_path = project_dir / "css" / "estilos.css"
            css_path.parent.mkdir(parents=True, exist_ok=True)
            css_path.write_text("body { color: black; }", encoding="utf-8")

            html_path = project_dir / "index.html"
            html_path.write_text(
                '<html><head><link rel="stylesheet" href="css/estilos.css"></head></html>',
                encoding="utf-8",
            )
            register_local_assets(session, asset_records)

            result = rewrite_local_asset_references(html_path, session, asset_records)
            rewritten_html = html_path.read_text(encoding="utf-8")

            self.assertEqual([], result)
            self.assertIn('href="css/estilos.css"', rewritten_html)
            self.assertNotIn(
                "Pagina%20de%20prueba%207/Pagina%20de%20prueba%207",
                rewritten_html,
            )
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_rewrites_missing_nested_path_relative_to_html_base(self) -> None:
        session = Session()
        asset_records = AssetRecords()
        try:
            before_root = session.get_area_root("before")
            project_dir = before_root / "Pagina de prueba 7"
            css_path = project_dir / "css" / "estilos.css"
            css_path.parent.mkdir(parents=True, exist_ok=True)
            css_path.write_text("body { color: black; }", encoding="utf-8")

            html_path = project_dir / "index.html"
            html_path.write_text(
                '<html><head><link rel="stylesheet" href="missing/estilos.css"></head></html>',
                encoding="utf-8",
            )
            register_local_assets(session, asset_records)

            result = rewrite_local_asset_references(html_path, session, asset_records)
            rewritten_html = html_path.read_text(encoding="utf-8")

            self.assertEqual(["css/estilos.css"], result)
            self.assertIn('href="css/estilos.css"', rewritten_html)
            self.assertNotIn(
                "Pagina%20de%20prueba%207/Pagina%20de%20prueba%207",
                rewritten_html,
            )
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_rewrites_urls_inside_external_css_files(self) -> None:
        session = Session()
        asset_records = AssetRecords()
        try:
            before_root = session.get_area_root("before")
            project_dir = before_root / "project"
            css_path = project_dir / "css" / "main.css"
            image_path = project_dir / "assets" / "hero.png"
            css_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.parent.mkdir(parents=True, exist_ok=True)
            css_path.write_text(
                ".hero { background-image: url(missing/hero.png); }",
                encoding="utf-8",
            )
            image_path.write_bytes(b"hero")

            html_path = project_dir / "index.html"
            html_path.write_text(
                '<html><head><link rel="stylesheet" href="css/main.css"></head></html>',
                encoding="utf-8",
            )
            register_local_assets(session, asset_records)

            result = rewrite_local_asset_references(html_path, session, asset_records)

            self.assertEqual(["../assets/hero.png"], result)
            self.assertIn(
                "url(../assets/hero.png)",
                css_path.read_text(encoding="utf-8"),
            )
            source = asset_records.find_asset(Path("project/assets/hero.png"))
            self.assertIsNotNone(source)
            self.assertEqual("project/assets/hero.png", source.source)
            css_asset = asset_records.find_asset(Path("project/css/main.css"))
            self.assertIsNotNone(css_asset)
            self.assertIsInstance(css_asset, LocalAsset)
            self.assertEqual("../assets/hero.png", css_asset.resource(source))
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
