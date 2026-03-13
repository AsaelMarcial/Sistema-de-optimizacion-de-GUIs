from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from engine.enums.scope.css_properties import CSS_PROPERTIES_BY_ID
from engine.enums.scope.html_elements import HTML_ELEMENTS_BY_ID
from engine.enums.scope.json_exports import build_scope_elements_payload, build_scope_properties_payload
from engine.file_handling.project_intake_pipeline import process_project_upload
from engine.file_handling.validators.archive_validators import validate_zip_members
from engine.rendering.rendering_pipeline import (
    analyze_screenshot_to_color_data,
    extract_render_snapshot,
)
from engine.rendering.utils.image_color_utils import pixels_to_color_frequency


FIXTURES_DIR = Path(__file__).parent / "fixtures"
RENDER_SCOPE_MATRIX = FIXTURES_DIR / "render_scope_matrix.html"


class InMemoryUpload:
    def __init__(self, filename: str, payload: bytes) -> None:
        self.filename = filename
        self._payload = payload

    def save(self, path: str) -> None:
        with open(path, "wb") as file:
            file.write(self._payload)


class EngineRefactorSmokeTests(unittest.TestCase):
    def test_scope_payloads_are_generated_from_python_source(self) -> None:
        properties_payload = build_scope_properties_payload()
        elements_payload = build_scope_elements_payload()

        self.assertIn("fill", CSS_PROPERTIES_BY_ID)
        self.assertIn("lighting-color", CSS_PROPERTIES_BY_ID)
        self.assertNotIn("margin", CSS_PROPERTIES_BY_ID)
        self.assertNotIn("pointer-events", CSS_PROPERTIES_BY_ID)

        self.assertIn("search", HTML_ELEMENTS_BY_ID)
        self.assertIn("selectedcontent", HTML_ELEMENTS_BY_ID)
        self.assertTrue(any(item["elementID"] == "img" for item in elements_payload["onScope"]))
        self.assertTrue(any(item["propertyID"] == "fill" for item in properties_payload["onScope"]))

    def test_validate_zip_members_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "unsafe.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("../escape.html", "<html></html>")
            with zipfile.ZipFile(zip_path, "r") as archive:
                error = validate_zip_members(archive)

        self.assertIn("ZIP inseguro", error or "")

    def test_process_project_upload_returns_typed_input(self) -> None:
        html_bytes = RENDER_SCOPE_MATRIX.read_bytes()
        upload = InMemoryUpload("render_scope_matrix.html", html_bytes)

        project_input = process_project_upload(upload, "testsess1")

        self.assertFalse(isinstance(project_input, str))
        assert not isinstance(project_input, str)
        self.assertEqual(project_input.html_filename, "render_scope_matrix.html")
        self.assertIn("Snapshot Matrix", project_input.html_content)

    def test_render_snapshot_contains_expected_scope_and_text(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        snapshot = extract_render_snapshot(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
        )

        tags = [node["identity"]["tag"] for node in snapshot["nodes"]]
        self.assertNotIn("script", tags)
        self.assertNotIn("source", tags)
        self.assertNotIn("track", tags)
        self.assertIn("search", tags)
        self.assertIn("ins", tags)
        self.assertIn("del", tags)
        self.assertIn("colgroup", tags)
        self.assertIn("selectedcontent", tags)

        image_nodes = [node for node in snapshot["nodes"] if node["identity"]["tag"] == "img"]
        self.assertEqual(len(image_nodes), 1)
        self.assertTrue(image_nodes[0]["flags"]["is_out_of_scope"])
        picture_nodes = [node for node in snapshot["nodes"] if node["identity"]["tag"] == "picture"]
        self.assertEqual(len(picture_nodes), 1)
        self.assertIn("related_media", picture_nodes[0]["identity"])

        title_nodes = [node for node in snapshot["nodes"] if node["identity"].get("id") == "title"]
        self.assertEqual(len(title_nodes), 1)
        self.assertEqual(title_nodes[0]["text"], "Snapshot Matrix")
        self.assertTrue(title_nodes[0]["identity"]["xpath"].startswith("/html[1]/body[1]"))

        for node in snapshot["nodes"]:
            self.assertNotIn("scope_group", node)
            self.assertIn("node_id", node)
            self.assertIn("is_leaf", node["flags"])
            self.assertIn("has_siblings", node["flags"])
            self.assertIn("is_stacking_context", node["flags"])

        node_ids = {node["node_id"] for node in snapshot["nodes"]}
        for node in snapshot["nodes"]:
            parent_id = node.get("parent_id")
            if parent_id:
                self.assertIn(parent_id, node_ids)
            for child_id in node.get("children_ids", []):
                self.assertIn(child_id, node_ids)

    def test_render_snapshot_filters_matching_styles_to_scope(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        snapshot = extract_render_snapshot(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
        )

        title_node = next(node for node in snapshot["nodes"] if node["identity"].get("id") == "title")
        tracked_styles = title_node["style_trace"].get("tracked_styles", {})
        all_declarations = [
            declaration["name"]
            for group in tracked_styles.values()
            for rule in group
            for declaration in rule.get("declarations", [])
        ]
        self.assertTrue(all(name in CSS_PROPERTIES_BY_ID for name in all_declarations))
        self.assertTrue(all("style_id" in rule for group in tracked_styles.values() for rule in group))
        self.assertIn("background_colors", title_node["styles"])
        self.assertIn("effective_background", title_node["styles"])

    def test_rules_used_are_global_and_deduplicated(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        snapshot = extract_render_snapshot(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
        )

        rules_used = snapshot["rules_used"]
        self.assertGreater(len(rules_used), 0)
        self.assertTrue(all("style_id" in rule for rule in rules_used))
        self.assertTrue(all("kind" in rule for rule in rules_used))
        self.assertTrue(all("declarations" in rule for rule in rules_used))
        self.assertTrue(all("node_ids" in rule or "usage_count" in rule for rule in rules_used))
        self.assertTrue(all("coverage" not in rule for rule in rules_used))

        unique_keys = {
            (
                rule.get("kind"),
                rule.get("origin"),
                rule.get("style_sheet_id"),
                rule.get("selector_text"),
                tuple((decl["name"], str(decl["value"])) for decl in rule["declarations"]),
            )
            for rule in rules_used
        }
        self.assertEqual(len(unique_keys), len(rules_used))

    def test_palette_contains_directly_applied_colors(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        snapshot = extract_render_snapshot(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
        )

        palette = snapshot["palette"]
        self.assertGreater(len(palette), 0)
        self.assertTrue(all("color_id" in entry for entry in palette))
        self.assertTrue(all("value" in entry for entry in palette))
        self.assertTrue(all("usage" in entry for entry in palette))
        self.assertTrue(
            any(
                usage["property"] == "color" and usage["tag"] == "h1"
                for entry in palette
                for usage in entry["usage"]
            )
        )

    def test_analyze_screenshot_to_color_data_returns_color_frequencies(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        color_data = analyze_screenshot_to_color_data(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            session_id="testsess3",
        )

        self.assertIsInstance(color_data, list)
        self.assertGreater(len(color_data), 0)
        self.assertTrue(all("color" in item and "count" in item for item in color_data))

    def test_pixels_to_color_frequency_uses_canonical_module(self) -> None:
        color_data = pixels_to_color_frequency(
            [[[255, 0, 0], [255, 0, 0]], [[0, 0, 255], [255, 0, 0]]]
        )
        self.assertEqual(color_data[0]["color"], [255, 0, 0])
        self.assertEqual(color_data[0]["count"], 3)


if __name__ == "__main__":
    unittest.main()
