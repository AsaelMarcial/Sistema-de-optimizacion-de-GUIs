from __future__ import annotations

import importlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from app import create_app
from engine.enums.scope.css_properties import CSS_PROPERTIES_BY_ID
from engine.enums.scope.html_elements import HTML_ELEMENTS_BY_ID
from engine.enums.scope.json_exports import build_scope_elements_payload, build_scope_properties_payload
from engine.models.prototype_structural_extractor.snapshot_models import SnapshotOptions
from engine.models.pipeline_context import PipelineContext
from engine.services.color_processing.material_quantization_service import (
    get_material_quantization_assessment,
)
from engine.services.color_processing.pixel_frequency_service import pixels_to_color_frequency
from engine.services.color_processing.pixel_frequency_service import (
    pixels_to_color_statistics,
)
from engine.services.file_handling.file_handler import load_project_input
from engine.services.prototype_structural_extractor.render_snapshot_service import (
    capture_prototype_state_artifacts,
    extract_prototype_state_snapshot,
)
from engine.validators.file_handling.archive_validators import validate_zip_members
from engine.pipeline.pipeline import run_pipeline


FIXTURES_DIR = Path(__file__).parent / "fixtures"
RENDER_SCOPE_MATRIX = FIXTURES_DIR / "render_scope_matrix.html"
STAGES_DIR = Path("engine/pipeline/stages")


class InMemoryUpload:
    def __init__(self, filename: str, payload: bytes) -> None:
        self.filename = filename
        self._payload = payload

    def save(self, path: str) -> None:
        with open(path, "wb") as file:
            file.write(self._payload)


class EngineRefactorSmokeTests(unittest.TestCase):
    def test_no_legacy_namespace_or_service_imports_remain(self) -> None:
        blocked_tokens = (
            "engine.core",
            "engine.rendering",
            "session_workspace_service",
            "upload_ingestion_service",
            "project_structure_service",
            "session_cleanup_service",
            "engine.file_handling.models",
            "engine.file_handling.services",
            "engine.file_handling.validators",
            "engine.color_processing.models",
            "engine.color_processing.services",
            "engine.environmental_assessment.models",
            "engine.environmental_assessment.services",
            "engine.prototype_structural_extractor.models",
            "engine.prototype_structural_extractor.services",
            "engine.recommendations.models",
            "engine.transformation.services",
            "engine.pipeline.services",
            "engine.analysis.utils.html_parser",
            "engine.services.color_service",
            "engine.services.debug_trace_service",
            "engine.services.results_compiler_service",
            "engine.services.file_handling.asset_staging_service",
            "engine.services.file_handling.artifact_storage_service",
        )
        python_files = [path for path in Path("engine").rglob("*.py")] + [
            path for path in Path("app").rglob("*.py")
        ]
        for path in python_files:
            content = path.read_text(encoding="utf-8")
            for token in blocked_tokens:
                self.assertNotIn(token, content, msg=f"{token} still present in {path}")

    def test_final_architecture_removes_core_and_rendering_compatibility(self) -> None:
        self.assertFalse((Path("engine/core")).exists())
        self.assertFalse((Path("engine/rendering")).exists())
        self.assertFalse((Path("engine/pipeline/stages/render_stage.py")).exists())
        self.assertTrue((Path("engine/models/legacy")).exists())
        routes_content = Path("app/routes.py").read_text(encoding="utf-8")
        self.assertIn("engine.pipeline.pipeline", routes_content)

    def test_pipeline_module_exposes_only_run_pipeline_as_runner_entrypoint(self) -> None:
        pipeline_module = importlib.import_module("engine.pipeline.pipeline")
        self.assertTrue(hasattr(pipeline_module, "run_pipeline"))
        self.assertFalse(hasattr(pipeline_module, "run_engine_pipeline"))
        self.assertFalse(hasattr(pipeline_module, "analyze_prototype_to_color_data"))

    def test_stage_modules_export_single_run_stage_function(self) -> None:
        expected_public_functions = {
            "color_processing": "run_color_processing_stage",
            "environmental_assessment": "run_environmental_assessment_stage",
            "file_handling": "run_file_handling_stage",
            "prototype_structural_extractor": "run_prototype_structural_extractor_stage",
            "recommendations": "run_recommendations_stage",
            "results": "run_results_stage",
            "transformation": "run_transformation_stage",
        }
        for package_name, function_name in expected_public_functions.items():
            package_dir = STAGES_DIR / package_name
            self.assertTrue(package_dir.is_dir(), msg=package_name)
            self.assertTrue((package_dir / "stage.py").exists(), msg=package_name)
            package_module = importlib.import_module(f"engine.pipeline.stages.{package_name}.stage")
            self.assertTrue(hasattr(package_module, function_name), msg=package_name)

    def test_stage_directory_no_longer_uses_flat_stage_files(self) -> None:
        for old_name in (
            "color_processing_stage.py",
            "environmental_assessment_stage.py",
            "file_handling_stage.py",
            "prototype_structural_extractor_stage.py",
            "recommendations_stage.py",
            "results_stage.py",
            "transformation_stage.py",
        ):
            self.assertFalse((STAGES_DIR / old_name).exists(), msg=old_name)

    def test_analysis_module_only_keeps_optional_html_parser(self) -> None:
        self.assertFalse((Path("engine/analysis")).exists())
        self.assertTrue((Path("engine/utils/html_utils.py")).exists())

    def test_pipeline_context_contains_shared_runtime_state_fields(self) -> None:
        context = PipelineContext(file=None)
        self.assertEqual(context.trace.__class__.__name__, "DebugTrace")
        self.assertTrue(hasattr(context, "project_input"))
        self.assertTrue(hasattr(context, "workspace"))
        self.assertTrue(hasattr(context, "original_artifacts"))
        self.assertTrue(hasattr(context, "environmental_artifacts"))
        self.assertTrue(hasattr(context, "footprint"))
        self.assertTrue(hasattr(context, "environmental_assessment"))
        self.assertTrue(hasattr(context, "heuristics_results"))
        self.assertTrue(hasattr(context, "results"))
        self.assertTrue(hasattr(context, "error"))

    def test_color_processing_uses_models_package(self) -> None:
        self.assertFalse((Path("engine/color_processing/models.py")).exists())
        self.assertFalse((Path("engine/color_processing/models")).exists())
        self.assertTrue((Path("engine/models/color_processing")).is_dir())
        self.assertTrue(
            (Path("engine/models/color_processing/color_processing_models.py")).exists()
        )
        self.assertFalse(
            (Path("engine/models/color_processing/pixel_color_frequency.py")).exists()
        )
        self.assertFalse(
            (Path("engine/models/color_processing/pixel_color_statistic.py")).exists()
        )
        self.assertFalse(
            (
                Path(
                    "engine/models/color_processing/material_quantization_assessment.py"
                )
            ).exists()
        )
        self.assertTrue((Path("engine/utils")).exists())
        self.assertTrue((Path("engine/validators")).exists())

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

    def test_load_project_input_returns_typed_input(self) -> None:
        html_bytes = RENDER_SCOPE_MATRIX.read_bytes()
        upload = InMemoryUpload("render_scope_matrix.html", html_bytes)

        project_input = load_project_input(upload, "testsess1")

        self.assertFalse(isinstance(project_input, str))
        assert not isinstance(project_input, str)
        self.assertEqual(project_input.html_filename, "render_scope_matrix.html")
        self.assertIn("Snapshot Matrix", project_input.html_content)

    def test_render_snapshot_contains_expected_scope_and_text(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        snapshot = extract_prototype_state_snapshot(
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
        snapshot = extract_prototype_state_snapshot(
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
        snapshot = extract_prototype_state_snapshot(
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
        snapshot = extract_prototype_state_snapshot(
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

    def test_capture_prototype_state_artifacts_returns_color_frequencies(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        artifacts = capture_prototype_state_artifacts(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(include_color_frequencies=True),
            session_id="testsess3",
        )
        color_data = artifacts.color_frequencies or []

        self.assertIsInstance(color_data, list)
        self.assertGreater(len(color_data), 0)
        self.assertTrue(all("color" in item and "count" in item for item in color_data))

    def test_pixels_to_color_frequency_uses_canonical_module(self) -> None:
        color_data = pixels_to_color_frequency(
            [[[255, 0, 0], [255, 0, 0]], [[0, 0, 255], [255, 0, 0]]]
        )
        self.assertEqual(color_data[0]["color"], [255, 0, 0])
        self.assertEqual(color_data[0]["count"], 3)

    def test_pixel_color_statistics_include_percentage(self) -> None:
        color_data = pixels_to_color_statistics(
            [[[255, 0, 0], [255, 0, 0]], [[0, 0, 255], [255, 0, 0]]]
        )
        self.assertEqual(color_data[0]["color_id"], "pixel-color-1")
        self.assertEqual(color_data[0]["count"], 3)
        self.assertAlmostEqual(color_data[0]["percentage"], 75.0)

    def test_material_quantization_assessment_is_available(self) -> None:
        assessment = get_material_quantization_assessment().to_dict()
        self.assertTrue(assessment["recommended"])
        self.assertEqual(assessment["recommended_quantizer"], "QuantizerCelebi (Wu + Wsmeans)")
        self.assertEqual(tuple(assessment["recommended_size"]), (128, 128))

    def test_run_pipeline_stops_on_missing_file(self) -> None:
        results, error = run_pipeline(None)
        self.assertIsNone(results)
        self.assertEqual(error, "No se seleccionó ningún archivo.")

    def test_run_pipeline_produces_results_with_recommendations(self) -> None:
        app = create_app()
        upload = InMemoryUpload("render_scope_matrix.html", RENDER_SCOPE_MATRIX.read_bytes())
        with app.test_request_context("/results", method="POST"):
            results, error = run_pipeline(upload)

        self.assertIsNone(error)
        assert results is not None
        self.assertIn("recommendations", results)
        self.assertIn("items", results["recommendations"])
        self.assertIn("render_snapshot", results)
        self.assertEqual(results["render_snapshot"]["artifact"], "render_snapshot_original.json")

    def test_placeholder_gitkeeps_are_removed_from_cleaned_domains(self) -> None:
        forbidden_gitkeeps = (
            Path("engine/recommendations/models/.gitkeep"),
            Path("engine/recommendations/rules/.gitkeep"),
            Path("engine/recommendations/services/.gitkeep"),
            Path("engine/recommendations/utils/.gitkeep"),
            Path("engine/recommendations/validators/.gitkeep"),
            Path("engine/transformation/models/.gitkeep"),
            Path("engine/transformation/utils/.gitkeep"),
            Path("engine/transformation/validators/.gitkeep"),
            Path("engine/environmental_assessment/validators/.gitkeep"),
            Path("engine/file_handling/utils/.gitkeep"),
        )
        for path in forbidden_gitkeeps:
            self.assertFalse(path.exists(), msg=str(path))

    def test_root_layer_topology_is_present(self) -> None:
        expected_paths = (
            Path("engine/models/debug_trace.py"),
            Path("engine/models/file_handling"),
            Path("engine/models/color_processing"),
            Path("engine/models/environmental_assessment"),
            Path("engine/models/prototype_structural_extractor"),
            Path("engine/models/recommendations"),
            Path("engine/services/file_handling"),
            Path("engine/services/color_processing"),
            Path("engine/services/environmental_assessment"),
            Path("engine/services/prototype_structural_extractor"),
            Path("engine/services/transformation"),
            Path("engine/validators/file_handling"),
            Path("engine/utils/color_utils.py"),
            Path("engine/utils/file_utils.py"),
            Path("engine/utils/html_utils.py"),
            Path("engine/utils/image_utils.py"),
            Path("engine/utils/serialization_utils.py"),
            Path("engine/utils/fs_utils.py"),
        )
        for path in expected_paths:
            self.assertTrue(path.exists(), msg=str(path))

    def test_domain_local_layers_are_removed(self) -> None:
        removed_paths = (
            Path("engine/file_handling/models.py"),
            Path("engine/file_handling/services"),
            Path("engine/file_handling/validators"),
            Path("engine/color_processing/models"),
            Path("engine/color_processing/services"),
            Path("engine/environmental_assessment/models"),
            Path("engine/environmental_assessment/services"),
            Path("engine/prototype_structural_extractor/models"),
            Path("engine/prototype_structural_extractor/services"),
            Path("engine/recommendations/models"),
            Path("engine/transformation/services"),
            Path("engine/analysis"),
            Path("engine/pipeline/services"),
            Path("engine/file_handling"),
            Path("engine/color_processing"),
            Path("engine/environmental_assessment"),
            Path("engine/prototype_structural_extractor"),
            Path("engine/transformation"),
            Path("engine/recommendations"),
            Path("engine/services/color_service.py"),
            Path("engine/services/debug_trace_service.py"),
            Path("engine/services/results_compiler_service.py"),
            Path("engine/services/file_handling/asset_staging_service.py"),
            Path("engine/services/file_handling/artifact_storage_service.py"),
        )
        for path in removed_paths:
            self.assertFalse(path.exists(), msg=str(path))

    def test_legacy_wrapper_symbols_are_removed(self) -> None:
        page_capture_content = Path(
            "engine/services/prototype_structural_extractor/page_capture_service.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("def render_gui(", page_capture_content)
        self.assertFalse(Path("engine/transformation/transformations_pipeline.py").exists())
        self.assertFalse(Path("engine/file_handling/project_intake_pipeline.py").exists())
        self.assertFalse(Path("engine/environmental_assessment/environmental_assessment_pipeline.py").exists())
        self.assertFalse(Path("engine/prototype_structural_extractor/prototype_state_pipeline.py").exists())

    def test_wrapper_package_inits_are_removed(self) -> None:
        removed_inits = (
            Path("engine/pipeline/stages/color_processing/__init__.py"),
            Path("engine/pipeline/stages/environmental_assessment/__init__.py"),
            Path("engine/pipeline/stages/file_handling/__init__.py"),
            Path("engine/pipeline/stages/prototype_structural_extractor/__init__.py"),
            Path("engine/pipeline/stages/recommendations/__init__.py"),
            Path("engine/pipeline/stages/results/__init__.py"),
            Path("engine/pipeline/stages/transformation/__init__.py"),
            Path("engine/services/file_handling/__init__.py"),
            Path("engine/services/color_processing/__init__.py"),
            Path("engine/services/environmental_assessment/__init__.py"),
            Path("engine/services/prototype_structural_extractor/__init__.py"),
            Path("engine/services/transformation/__init__.py"),
            Path("engine/utils/__init__.py"),
            Path("engine/models/file_handling/__init__.py"),
            Path("engine/models/color_processing/__init__.py"),
            Path("engine/models/environmental_assessment/__init__.py"),
            Path("engine/models/prototype_structural_extractor/__init__.py"),
            Path("engine/models/recommendations/__init__.py"),
            Path("engine/validators/file_handling/__init__.py"),
            Path("engine/enums/scope/__init__.py"),
        )
        for path in removed_inits:
            self.assertFalse(path.exists(), msg=str(path))

    def test_pixel_frequency_service_only_keeps_domain_entrypoints(self) -> None:
        content = Path("engine/services/color_processing/pixel_frequency_service.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("def load_image_array(", content)
        self.assertNotIn("def json_default_numpy_serializer(", content)


if __name__ == "__main__":
    unittest.main()
