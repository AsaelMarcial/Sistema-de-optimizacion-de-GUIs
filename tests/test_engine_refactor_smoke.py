import importlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from coloraide.everything import ColorAll

from app import create_app
from engine.adapters.browser.snapshot_analyzer import (
    capture_prototype_state_artifacts,
    extract_prototype_state_snapshot,
)
from engine.adapters.file_system.file_handler import load_project_input
from engine.adapters.utils.palette_preview import render_palette_preview
from engine.adapters.utils.screenshot import pixels_to_color_frequency, pixels_to_color_records
from engine.domain.data.material_quantization import (
    get_material_quantization_assessment,
)
from engine.domain.data.css_properties import CSS_PROPERTIES_BY_ID
from engine.domain.data.html_elements import HTML_ELEMENTS_BY_ID
from engine.domain.data.web_colors import WebColor, nearest_web_color
from engine.domain.enums.scope.json_exports import (
    build_scope_elements_payload,
    build_scope_properties_payload,
)
from engine.domain.enums.types.color import (
    ColorConfirmationStatus,
    ColorFamilyType,
    PaletteRoleBias,
)
from engine.domain.enums.types.elements import ElementSourceKind
from engine.domain.enums.types.style import (
    StyleKind,
    StyleOrigin,
    StyleResolutionStatus,
    StyleUsageStatus,
)
from engine.domain.enums.types.transformations import (
    TransformationKind,
    TransformationStatus,
)
from engine.domain.models.environmental_assessment.carbon_footprint import (
    CarbonFootprintModel,
    assess_interface,
    calculate,
)
from engine.domain.models.environmental_assessment.energy_consumption import (
    EnergyModel,
    calculate_power,
    estimate_current,
)
from engine.domain.models.color import ColorInventoryModel
from engine.domain.models.palette import TonalPaletteModel
from engine.domain.models.session import SessionModel
from engine.domain.models.snapshot import SnapshotOptions
from engine.domain.models.style import StyleInventoryModel
from engine.domain.models.inventory_graph import InventoryGraphModel
from engine.domain.models.token import (
    Token,
    TokenInventory,
    TokenState,
    TokenValidationModel,
    TokenValidationStatus,
)
from engine.domain.utils.coloraide import (
    color_to_hex,
    composite_over,
    contrast_ratio,
    delta_e_distance,
    hct_coords,
)
from engine.domain.utils.formatters import color_frequency_to_statistics
from engine.domain.utils.palette_analysis import build_palette_analysis
from engine.domain.utils.tokenization import build_token_inventory
from engine.validators.file_handling.archive_validators import validate_zip_members
from engine.validators.token_rules import apply_token_rules
from engine.pipeline.context import PipelineContext
from engine.pipeline.pipeline import run_pipeline
from engine.pipeline.stages.assemble_results import _build_results_view
from engine.pipeline.stages.build_inventories import _build_element_color_properties


FIXTURES_DIR = Path(__file__).parent / "fixtures"
RENDER_SCOPE_MATRIX = FIXTURES_DIR / "render_scope_matrix.html"
RENDER_CASCADE_MATRIX = FIXTURES_DIR / "render_cascade_matrix.html"
STAGES_DIR = Path("engine/pipeline/stages")


class InMemoryUpload:
    def __init__(self, filename: str, payload: bytes) -> None:
        self.filename = filename
        self._payload = payload

    def save(self, path: str) -> None:
        with open(path, "wb") as file:
            file.write(self._payload)


class EngineRefactorSmokeTests(unittest.TestCase):
    def _snapshot_fixture_projection(self, fixture_path: Path) -> dict[str, object]:
        html_content = fixture_path.read_text(encoding="utf-8")
        artifacts = capture_prototype_state_artifacts(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(include_color_frequencies=False, capture_screenshot=False),
        )
        return {
            "snapshot": artifacts.snapshot.to_dict(),
            "elements_inventory": artifacts.snapshot.build_elements_inventory().to_dict(),
            "styles_inventory": (
                artifacts.styles_inventory_seed.to_dict()
                if artifacts.styles_inventory_seed is not None
                else []
            ),
            "palette": (
                artifacts.colors_inventory_seed.to_palette_dicts()
                if artifacts.colors_inventory_seed is not None
                else []
            ),
        }

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
            "engine." "services.color_service",
            "engine." "services.debug_trace_service",
            "engine." "services.results_compiler_service",
            "engine." "services.file_handling.asset_staging_service",
            "engine." "services.file_handling.artifact_storage_service",
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
            "prepare_project_session.py": "run_stage",
            "capture_original_state.py": "run_stage",
            "build_color_scheme.py": "run_stage",
            "assess_original_environmental_impact.py": "run_stage",
            "transform_source_project.py": "run_stage",
            "assess_transformed_environmental_impact.py": "run_stage",
            "assemble_results.py": "run_stage",
            "build_inventories.py": "run_stage",
            "enrich_color_inventory.py": "run_stage",
            "map_color_inventory_to_scheme.py": "run_stage",
            "set_tokens.py": "run_stage",
            "check_tokens.py": "run_stage",
        }
        for module_name, function_name in expected_public_functions.items():
            module_path = STAGES_DIR / module_name
            self.assertTrue(module_path.exists(), msg=module_name)
            package_module = importlib.import_module(
                f"engine.pipeline.stages.{module_name.removesuffix('.py')}"
            )
            self.assertTrue(hasattr(package_module, function_name), msg=module_name)
            self.assertTrue(hasattr(package_module, "CONTRACT"), msg=f"{module_name} missing CONTRACT")

    def test_stage_directory_is_flat_without_nested_stage_packages(self) -> None:
        for removed_dir in (
            "color_processing",
            "environmental_assessment",
            "file_handling",
            "prototype_structural_extractor",
            "recommendations",
            "results",
            "transformation",
        ):
            self.assertFalse((STAGES_DIR / removed_dir).exists(), msg=removed_dir)

    def test_analysis_module_is_removed_without_optional_html_parser_wrapper(self) -> None:
        self.assertFalse((Path("engine/analysis")).exists())
        self.assertFalse((Path("engine/utils/html_utils.py")).exists())

    def test_pipeline_context_uses_hierarchical_runtime_state(self) -> None:
        context = PipelineContext(file=None)
        self.assertEqual(context.trace.__class__.__name__, "DebugTrace")
        context.set("session.input.html.name", "index.html")
        context.set("elements.inventory", ())
        self.assertEqual(context.get("session.input.html.name"), "index.html")
        self.assertTrue(context.has("elements.inventory"))
        self.assertIsInstance(context.snapshot(), dict)
        self.assertIsNone(context.get("results"))
        self.assertTrue(hasattr(context, "error"))

    def test_session_model_builds_related_input_output_and_artifact_directories(self) -> None:
        session = SessionModel.build(
            session_id="abc12345",
            session_dirname="session_abc12345",
            base_dir="workspace/sessions",
        )

        self.assertEqual(session.input.kind.value, "input")
        self.assertEqual(session.output.kind.value, "output")
        self.assertEqual(session.artifacts.kind.value, "artifacts")
        self.assertTrue(session.input.path.endswith("session_abc12345\\input"))
        self.assertTrue(session.output.path.endswith("session_abc12345\\output"))
        self.assertTrue(session.artifacts.path.endswith("session_abc12345\\artifacts"))

    def test_color_processing_uses_canonical_domain_and_adapter_modules(self) -> None:
        self.assertFalse((Path("engine/color_processing/models.py")).exists())
        self.assertFalse((Path("engine/color_processing/models")).exists())
        self.assertTrue((Path("engine/domain/models/palette.py")).exists())
        self.assertTrue((Path("engine/domain/utils/palette_analysis.py")).exists())
        self.assertTrue((Path("engine/adapters/utils/screenshot.py")).exists())
        self.assertFalse((Path("engine/models/color_processing")).exists())
        self.assertFalse((Path("engine/utils")).exists())
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
        fill_item = next(
            item for item in properties_payload["onScope"] if item["propertyID"] == "fill"
        )
        background_item = next(
            item
            for item in properties_payload["onScope"]
            if item["propertyID"] == "background-color"
        )
        lighting_item = next(
            item
            for item in properties_payload["onScope"]
            if item["propertyID"] == "lighting-color"
        )
        border_item = next(
            item for item in properties_payload["onScope"] if item["propertyID"] == "border-color"
        )
        outline_item = next(
            item for item in properties_payload["onScope"] if item["propertyID"] == "outline-color"
        )
        column_rule_item = next(
            item
            for item in properties_payload["onScope"]
            if item["propertyID"] == "column-rule-color"
        )
        self.assertEqual(fill_item["colorRole"], "foreground")
        self.assertEqual(background_item["colorRole"], "background")
        self.assertEqual(lighting_item["colorRole"], "other")
        self.assertEqual(border_item["colorRole"], "foreground")
        self.assertEqual(outline_item["colorRole"], "foreground")
        self.assertEqual(column_rule_item["colorRole"], "foreground")

    def test_closed_domain_enums_are_available(self) -> None:
        self.assertEqual(StyleKind.INLINE.value, "inline")
        self.assertEqual(StyleOrigin.AUTHOR.value, "author")
        self.assertEqual(StyleUsageStatus.USED.value, "used")
        self.assertEqual(StyleResolutionStatus.UNRESOLVED.value, "unresolved")
        self.assertEqual(ElementSourceKind.INHERITED.value, "inherited")
        self.assertEqual(ColorFamilyType.CHROMATIC.value, "chromatic")
        self.assertEqual(ColorConfirmationStatus.CONFIRMED.value, "confirmed")
        self.assertEqual(PaletteRoleBias.BACKGROUND.value, "background")
        self.assertEqual(TransformationKind.HEURISTIC.value, "heuristic")
        self.assertEqual(TransformationStatus.APPLIED.value, "applied")

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
        self.assertEqual(project_input.session.session_id, "testsess1")
        self.assertEqual(project_input.workspace.session_id, "testsess1")

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

        image_nodes = [
            node for node in snapshot["nodes"] if node["identity"]["tag"] == "img"
        ]
        self.assertEqual(len(image_nodes), 1)
        self.assertTrue(image_nodes[0]["flags"]["is_out_of_scope"])
        picture_nodes = [
            node
            for node in snapshot["nodes"]
            if node["identity"]["tag"] == "picture"
        ]
        self.assertEqual(len(picture_nodes), 1)
        self.assertIn("related_media", picture_nodes[0]["identity"])

        title_nodes = [
            node
            for node in snapshot["nodes"]
            if node["identity"].get("id") == "title"
        ]
        self.assertEqual(len(title_nodes), 1)
        self.assertEqual(title_nodes[0]["text"], "Snapshot Matrix")
        self.assertTrue(title_nodes[0]["identity"]["xpath"].startswith("/html[1]/body[1]"))
        self.assertFalse(title_nodes[0]["flags"]["is_text_node"])

        self.assertIn("nodes", snapshot)
        self.assertIn("tree", snapshot)
        self.assertNotIn("elements_inventory", snapshot)
        self.assertNotIn("styles_inventory", snapshot)
        self.assertNotIn("rules_used", snapshot)

        for node in snapshot["nodes"]:
            self.assertIn("node_id", node)
            self.assertIn("is_leaf", node["flags"])
            self.assertIn("has_siblings", node["flags"])
            self.assertIn("is_stacking_context", node["flags"])
            self.assertIn("computed_styles", node)
            self.assertNotIn("style_trace", node)

        node_ids = {node["node_id"] for node in snapshot["nodes"]}
        for node in snapshot["nodes"]:
            parent_id = node.get("parent_id")
            if parent_id:
                self.assertIn(parent_id, node_ids)
            for child_id in node.get("children_ids", []):
                self.assertIn(child_id, node_ids)

    def test_render_snapshot_filters_matching_styles_to_scope(self) -> None:
        projection = self._snapshot_fixture_projection(RENDER_SCOPE_MATRIX)
        snapshot = projection["snapshot"]
        assert isinstance(snapshot, dict)
        styles_inventory = projection["styles_inventory"]
        assert isinstance(styles_inventory, list)

        title_node = next(
            node for node in snapshot["nodes"] if node["identity"].get("id") == "title"
        )
        all_declarations = [
            declaration["name"]
            for style in styles_inventory
            for declaration in style.get("declarations", [])
        ]
        self.assertTrue(all(name in CSS_PROPERTIES_BY_ID for name in all_declarations))
        self.assertIn("color", title_node["computed_styles"])
        self.assertIn("background-color", title_node["computed_styles"])
        self.assertEqual(title_node["computed_styles"]["color"]["kind"], "inline")
        self.assertEqual(
            title_node["computed_styles"]["background-color"]["declared_property"],
            "background-color",
        )
        self.assertIn("effective_background", title_node["styles"])
        self.assertNotIn("background_colors", title_node["styles"])
        self.assertEqual(
            list(title_node["computed_styles"]["color"].keys()),
            ["style_id", "kind", "declared_property", "resolution_status", "computed_value"],
        )
        self.assertEqual(
            title_node["computed_styles"]["color"]["resolution_status"],
            "exact_match",
        )

    def test_styles_inventory_is_global_and_deduplicated(self) -> None:
        projection = self._snapshot_fixture_projection(RENDER_SCOPE_MATRIX)
        styles_inventory = projection["styles_inventory"]
        assert isinstance(styles_inventory, list)
        self.assertGreater(len(styles_inventory), 0)
        self.assertTrue(all("style_id" in rule for rule in styles_inventory))
        self.assertTrue(all("kind" in rule for rule in styles_inventory))
        self.assertTrue(all("declarations" in rule for rule in styles_inventory))
        self.assertTrue(all("node_ids" in rule or "usage_count" in rule for rule in styles_inventory))
        self.assertTrue(all("coverage" not in rule for rule in styles_inventory))

        unique_keys = {
            (
                rule.get("kind"),
                rule.get("origin"),
                rule.get("style_sheet_id"),
                rule.get("selector_text"),
                tuple(sorted((rule.get("source_range") or {}).items())),
                rule.get("layer_name"),
                rule.get("layer_order"),
                rule.get("source_url"),
                tuple((decl["name"], str(decl["value"])) for decl in rule["declarations"]),
            )
            for rule in styles_inventory
        }
        self.assertLessEqual(len(unique_keys), len(styles_inventory))
        self.assertTrue(all(rule.get("origin") != "user-agent" for rule in styles_inventory))
        self.assertTrue(
            all(
                not (
                    rule.get("origin") == "user-agent"
                    and any(declaration["name"] == "display" for declaration in rule["declarations"])
                )
                for rule in styles_inventory
            )
        )

    def test_cascade_resolution_links_computed_properties_to_real_styles(self) -> None:
        projection = self._snapshot_fixture_projection(RENDER_CASCADE_MATRIX)
        snapshot = projection["snapshot"]
        styles_inventory = projection["styles_inventory"]
        assert isinstance(snapshot, dict)
        assert isinstance(styles_inventory, list)

        elements = {
            node["identity"].get("id"): node
            for node in snapshot["nodes"]
            if node["identity"].get("id")
        }
        styles_by_id = {
            style["style_id"]: style
            for style in styles_inventory
        }

        winner_color = elements["winner"]["computed_styles"]["color"]
        self.assertEqual(winner_color["kind"], "external")
        self.assertEqual(winner_color["resolution_status"], "exact_match")
        self.assertEqual(winner_color["declared_property"], "color")
        self.assertEqual(styles_by_id[winner_color["style_id"]]["selector_text"], "#winner")

        important_color = elements["important"]["computed_styles"]["color"]
        if important_color.get("style_id"):
            self.assertEqual(important_color["kind"], "external")
            self.assertEqual(important_color["resolution_status"], "exact_match")
            self.assertEqual(important_color["declared_property"], "color")
            self.assertEqual(styles_by_id[important_color["style_id"]]["selector_text"], "p")
        else:
            self.assertEqual(important_color["resolution_status"], "unresolved")

        inherited_color = elements["inherit-child"]["computed_styles"]["color"]
        self.assertEqual(inherited_color["kind"], "inherited")
        self.assertEqual(inherited_color["declared_property"], "color")
        self.assertEqual(
            inherited_color["inherited_from_element_id"],
            elements["inherit-parent"]["node_id"],
        )

        shorthand_background = elements["shorthand"]["computed_styles"]["background-color"]
        self.assertIn(
            shorthand_background["declared_property"],
            {"background", "background-color"},
        )
        outline_color = elements["outline"]["computed_styles"]["outline-color"]
        self.assertIn(outline_color["declared_property"], {"outline", "outline-color"})
        current_border = elements["current-color"]["computed_styles"]["border-top-color"]
        self.assertIn(
            current_border["declared_property"],
            {"border-color", "border-top-color"},
        )

    def test_elements_inventory_computed_styles_have_style_or_unresolved(self) -> None:
        projection = self._snapshot_fixture_projection(RENDER_SCOPE_MATRIX)
        styles_inventory = projection["styles_inventory"]
        elements_inventory = projection["elements_inventory"]
        assert isinstance(styles_inventory, list)
        assert isinstance(elements_inventory, list)

        style_ids = {style["style_id"] for style in styles_inventory}
        for element in elements_inventory:
            for payload in element.get("computed_styles", {}).values():
                self.assertIn("computed_value", payload)
                self.assertTrue("style_id" in payload or payload.get("resolution_status") == "unresolved")
                if "style_id" in payload:
                    self.assertIn(payload["style_id"], style_ids)

    def test_snapshot_omits_unmatched_default_computed_properties(self) -> None:
        projection = self._snapshot_fixture_projection(RENDER_CASCADE_MATRIX)
        snapshot = projection["snapshot"]
        assert isinstance(snapshot, dict)

        elements = {
            node["identity"].get("id"): node
            for node in snapshot["nodes"]
            if node["identity"].get("id")
        }

        shorthand_styles = elements["shorthand"]["computed_styles"]
        self.assertIn("background-color", shorthand_styles)
        self.assertNotIn("background-repeat", shorthand_styles)
        self.assertNotIn("background-position", shorthand_styles)
        self.assertNotIn("background-clip", shorthand_styles)
        self.assertNotIn("background-origin", shorthand_styles)
        self.assertNotIn("background-attachment", shorthand_styles)

        winner_styles = elements["winner"]["computed_styles"]
        self.assertNotIn("width", winner_styles)
        self.assertNotIn("height", winner_styles)
        self.assertNotIn("opacity", winner_styles)
        self.assertNotIn("position", winner_styles)
        self.assertNotIn("fill", winner_styles)
        self.assertNotIn("display", winner_styles)

    def test_snapshot_includes_raw_text_nodes_alongside_parent_elements(self) -> None:
        snapshot = extract_prototype_state_snapshot(
            html_content=RENDER_SCOPE_MATRIX.read_text(encoding="utf-8"),
            base_path=str(FIXTURES_DIR),
        )

        title_node = next(
            node for node in snapshot["nodes"] if node["identity"].get("id") == "title"
        )
        self.assertEqual(title_node["text"], "Snapshot Matrix")
        text_children = [
            node
            for node in snapshot["nodes"]
            if node["identity"]["tag"] == "#text" and node.get("parent_id") == title_node["node_id"]
        ]
        self.assertEqual(len(text_children), 1)
        self.assertEqual(text_children[0]["text"], "Snapshot Matrix")
        self.assertTrue(text_children[0]["flags"]["is_text_node"])

    def test_palette_contains_directly_applied_colors(self) -> None:
        projection = self._snapshot_fixture_projection(RENDER_SCOPE_MATRIX)
        palette = projection["palette"]
        assert isinstance(palette, list)
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
        palette_values = {entry["value"] for entry in palette}
        self.assertNotIn("rgba(0, 0, 0, 0.35)", palette_values)
        self.assertNotIn("rgba(0, 0, 0, 0.5)", palette_values)

        palette_usage_properties = {
            usage["property"]
            for entry in palette
            for usage in entry["usage"]
        }
        self.assertNotIn("border-top-color", palette_usage_properties)
        self.assertNotIn("border-right-color", palette_usage_properties)
        self.assertNotIn("border-bottom-color", palette_usage_properties)
        self.assertNotIn("border-left-color", palette_usage_properties)

        tracked_declarations = {
            declaration["name"]
            for rule in projection["styles_inventory"]
            for declaration in rule.get("declarations", [])
        }
        self.assertIn("box-shadow", tracked_declarations)
        self.assertIn("text-shadow", tracked_declarations)
        self.assertIn("filter", tracked_declarations)

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
        color_data = color_frequency_to_statistics(
            pixels_to_color_records(
                [[[255, 0, 0], [255, 0, 0]], [[0, 0, 255], [255, 0, 0]]]
            )
        )
        self.assertEqual(color_data[0]["color_id"], "pixel-color-1")
        self.assertEqual(color_data[0]["count"], 3)
        self.assertAlmostEqual(color_data[0]["percentage"], 75.0)

    def test_environmental_assessment_uses_immutable_models_and_functions(self) -> None:
        pixels = (
            {"color": [255, 255, 255], "count": 2},
            {"color": [0, 0, 0], "count": 1},
        )
        energy_model = EnergyModel.build_default()
        carbon_model = CarbonFootprintModel.build_default()

        current_a = estimate_current(pixels, energy_model)
        self.assertEqual(current_a, calculate_power(pixels, energy_model))
        assessment = calculate(
            current_a=current_a,
            time_hours=1,
            carbon_model=carbon_model,
            user_count=10,
            usage_hours=2,
        )
        interface_assessment = assess_interface(
            pixels,
            energy_model=energy_model,
            carbon_model=carbon_model,
            time_hours=1,
            user_count=10,
            usage_hours=2,
        )

        self.assertIn("energy_wh", assessment)
        self.assertIn("co2eq_per_use", assessment)
        self.assertAlmostEqual(interface_assessment["current_a"], current_a)

    def test_coloraide_dependency_supports_hct_distance_and_named_colors(self) -> None:
        color = ColorAll("#ff0000")
        self.assertIn("hct", ColorAll.CS_MAP)
        self.assertEqual(color.convert("hct").space(), "hct")
        self.assertGreater(color.delta_e(ColorAll("#0000ff"), method="2000"), 0)
        self.assertEqual(ColorAll("white").to_string(names=True), "white")

    def test_coloraide_helper_centralizes_distance_contrast_and_alpha_compositing(self) -> None:
        composited = composite_over("rgba(255 0 0 / 0.5)", "white")
        self.assertEqual(composited.space(), "srgb")
        self.assertGreater(contrast_ratio("black", "white"), 20.0)
        self.assertGreater(delta_e_distance("#ff0000", "#0000ff", method="2000"), 0.0)
        self.assertEqual(
            tuple(round(channel, 4) for channel in composited.coords()),
            (1.0, 0.5, 0.5),
        )

    def test_hct_coords_sanitize_achromatic_hue(self) -> None:
        self.assertEqual(hct_coords("#000000"), (0.0, 0.0, 0.0))

    def test_web_color_enum_and_nearest_lookup_are_available(self) -> None:
        self.assertEqual(WebColor.WHITE.hex_value, "#ffffff")
        match = nearest_web_color((254, 254, 254))
        self.assertEqual(match.color_name, "white")
        self.assertEqual(match.wikipedia_family, "Colores blancos")

    def test_tonal_palette_model_builds_seed_tones(self) -> None:
        palette = TonalPaletteModel.from_seed(
            palette_id="palette-chromatic-1",
            palette_type="chromatic",
            seed_hex="#ff0000",
            role_bias="foreground",
            semantic_weight=10,
            confirmed_pixel_count=25,
            seed_name="red",
            source_color_ids=("color-1",),
        )
        self.assertEqual(palette.seed_name, "red")
        self.assertGreater(len(palette.tones), 10)
        self.assertEqual(palette.tones[0].tone, 10)
        self.assertEqual(palette.tones[-1].tone, 98)
        self.assertEqual(palette.tones[-1].hex_value, color_to_hex(palette.tones[-1].rgb))

    def test_achromatic_tonal_palette_keeps_full_base_scale(self) -> None:
        palette = TonalPaletteModel.from_seed(
            palette_id="palette-achromatic-1",
            palette_type="achromatic",
            seed_hex="#ffffff",
            role_bias="background",
            semantic_weight=5,
            confirmed_pixel_count=50,
            seed_name="white",
            source_color_ids=("color-1",),
            chroma_override=6.0,
        )
        self.assertEqual(palette.tones[0].tone, 0)
        self.assertEqual(palette.tones[-1].tone, 100)

    def test_palette_analysis_produces_named_breakdown_and_core_palettes(self) -> None:
        palette_analysis = build_palette_analysis(
            snapshot_palette=(
                {
                    "color_id": "color-1",
                    "value": "rgb(255, 255, 255)",
                    "usage_count": 3,
                    "usage": [{"tag": "body", "property": "background-color", "count": 3}],
                },
                {
                    "color_id": "color-2",
                    "value": "rgb(255, 0, 0)",
                    "usage_count": 2,
                    "usage": [{"tag": "h1", "property": "color", "count": 2}],
                },
            ),
            pixel_color_frequencies=[
                {"color": [255, 255, 255], "count": 80},
                {"color": [255, 0, 0], "count": 20},
                {"color": [0, 200, 0], "count": 5},
            ],
            material_quantization_assessment=get_material_quantization_assessment(),
        ).to_dict()

        self.assertEqual(
            palette_analysis["core_palettes"]["achromatic_palette"]["palette_type"],
            "achromatic",
        )
        self.assertEqual(
            palette_analysis["core_palettes"]["chromatic_palettes"][0]["palette_type"],
            "chromatic",
        )
        self.assertEqual(
            palette_analysis["core_palettes"]["chromatic_palettes"][0]["tones"][0]["tone"],
            10,
        )
        self.assertEqual(
            palette_analysis["core_palettes"]["chromatic_palettes"][0]["tones"][-1]["tone"],
            98,
        )
        self.assertEqual(palette_analysis["named_color_breakdown"][0]["name"], "white")
        self.assertGreater(palette_analysis["residual_pixel_count"], 0)
        self.assertTrue(
            palette_analysis["semantic_colors"][0]["mapped_palette_id"].startswith(
                "palette-achromatic-"
            )
        )
        self.assertTrue(
            palette_analysis["semantic_colors"][1]["mapped_palette_id"].startswith(
                "palette-chromatic-"
            )
        )
        self.assertIn("background_color_usages", palette_analysis["semantic_colors"][0])
        self.assertIn("foreground_color_usages", palette_analysis["semantic_colors"][1])

    def test_palette_analysis_merges_same_family_colors_when_they_only_vary_by_tone(self) -> None:
        palette_analysis = build_palette_analysis(
            snapshot_palette=(
                {
                    "color_id": "color-1",
                    "value": "rgb(222, 155, 255)",
                    "usage_count": 3,
                    "usage": [{"tag": "input", "property": "background-color", "count": 3}],
                },
                {
                    "color_id": "color-2",
                    "value": "rgb(200, 0, 255)",
                    "usage_count": 2,
                    "usage": [{"tag": "button", "property": "background-color", "count": 2}],
                },
            ),
            pixel_color_frequencies=[
                {"color": [222, 155, 255], "count": 120},
                {"color": [200, 0, 255], "count": 90},
            ],
            material_quantization_assessment=get_material_quantization_assessment(),
        ).to_dict()

        chromatic_palettes = palette_analysis["core_palettes"]["chromatic_palettes"]
        self.assertEqual(len(chromatic_palettes), 1)
        self.assertEqual(chromatic_palettes[0]["display_name"], "Violet")

    def test_palette_analysis_ignores_colors_without_semantic_or_pixel_support(self) -> None:
        palette_analysis = build_palette_analysis(
            snapshot_palette=(
                {
                    "color_id": "color-1",
                    "value": "rgb(255, 255, 255)",
                    "usage_count": 5,
                    "usage": [{"tag": "body", "property": "background-color", "count": 5}],
                    "display_pixel_count": 90,
                },
                {
                    "color_id": "color-2",
                    "value": "rgb(255, 0, 0)",
                    "usage_count": 0,
                    "usage": [],
                    "display_pixel_count": 0,
                    "added_from_pixel_evidence": True,
                },
            ),
            pixel_color_frequencies=[
                {"color": [255, 255, 255], "count": 90},
                {"color": [255, 0, 0], "count": 3},
            ],
            material_quantization_assessment=get_material_quantization_assessment(),
        ).to_dict()

        self.assertEqual(len(palette_analysis["semantic_colors"]), 1)
        self.assertEqual(
            len(palette_analysis["core_palettes"]["chromatic_palettes"]),
            0,
        )

    def test_palette_preview_renderer_outputs_png(self) -> None:
        palette_analysis = build_palette_analysis(
            snapshot_palette=(
                {
                    "color_id": "color-1",
                    "value": "rgb(255, 255, 255)",
                    "usage_count": 3,
                    "usage": [{"tag": "body", "property": "background-color", "count": 3}],
                },
                {
                    "color_id": "color-2",
                    "value": "rgb(255, 0, 0)",
                    "usage_count": 2,
                    "usage": [{"tag": "h1", "property": "color", "count": 2}],
                },
            ),
            pixel_color_frequencies=[
                {"color": [255, 255, 255], "count": 80},
                {"color": [255, 0, 0], "count": 20},
            ],
            material_quantization_assessment=get_material_quantization_assessment(),
        ).to_dict()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "palette_preview.png"
            render_palette_preview(palette_analysis, str(output_path))

            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)

    def test_token_model_tracks_alias_assignments_and_validations(self) -> None:
        token = Token.semantic(
            path=("glow", "text", "color", "emphasis", "4"),
            alias_to="glow.color.neutral.100",
            resolved_value="#ffffff",
            element_key="text",
            property_id="color",
            value_label="emphasis.4",
            source_color_ids=("color-1",),
            source_element_ids=("node-1",),
            source_property_refs=("node-1:color",),
            assigned_element_ids=("node-1",),
            created_by_stage="tests",
        ).with_validation(
            TokenValidationModel(
                rule_id="text_contrast",
                status=TokenValidationStatus.FAILED,
                reason="contrast too low",
                metrics={"contrast": 3.2, "minimum": 4.5},
            )
        )

        self.assertTrue(token.is_semantic_alias)
        self.assertTrue(token.has_failed_validations)
        self.assertEqual(token.effective_assignment_count, 1)
        payload = token.to_dict()
        self.assertEqual(token.path_string, "glow.text.color.emphasis.4")
        self.assertEqual(payload["alias_to"], "glow.color.neutral.100")
        self.assertEqual(payload["validations"][0]["status"], "failed")
        self.assertEqual(payload["css_variable_name"], "--glow-text-color-emphasis-4")

    def test_inventory_graph_builds_relations_and_effective_backgrounds(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        artifacts = capture_prototype_state_artifacts(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(include_color_frequencies=False, capture_screenshot=False),
        )
        elements_inventory = _build_element_color_properties(
            artifacts.snapshot.build_elements_inventory(),
            ColorInventoryModel.build(artifacts.colors_inventory_seed),
        )
        styles_inventory = StyleInventoryModel.build(artifacts.styles_inventory_seed)
        colors_inventory = ColorInventoryModel.build(artifacts.colors_inventory_seed)
        graph = InventoryGraphModel.build(
            elements=elements_inventory,
            styles=styles_inventory,
            colors=colors_inventory,
        )

        title_entry = next(
            entry for entry in elements_inventory if entry.identity.id == "title"
        )
        parent = graph.parent_of(title_entry.node_id)
        self.assertIsNotNone(parent)
        assert parent is not None
        self.assertIn(title_entry.node_id, [child.node_id for child in graph.children_of(parent.node_id)])
        self.assertGreaterEqual(len(graph.ancestors_of(title_entry.node_id)), 1)
        effective_background = graph.effective_background_of(title_entry.node_id)
        self.assertIsNotNone(effective_background)
        assert effective_background is not None
        self.assertTrue(effective_background.hex_value.startswith("#"))
        effective_foreground = graph.effective_color_of(title_entry.node_id)
        self.assertIsNotNone(effective_foreground)
        surface_container = graph.surface_container_of(title_entry.node_id)
        self.assertIsNotNone(surface_container)
        self.assertTrue(
            isinstance(graph.adjacent_elements_of(title_entry.node_id), tuple)
        )

    def test_token_inventory_and_rules_build_from_existing_palette_and_inventory(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        artifacts = capture_prototype_state_artifacts(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(include_color_frequencies=True, capture_screenshot=False),
        )
        colors_inventory = ColorInventoryModel.build(artifacts.colors_inventory_seed)
        elements_inventory = _build_element_color_properties(
            artifacts.snapshot.build_elements_inventory(),
            colors_inventory,
        )
        styles_inventory = StyleInventoryModel.build(artifacts.styles_inventory_seed)
        palette_analysis = build_palette_analysis(
            snapshot_palette=colors_inventory.to_palette_dicts(),
            pixel_color_frequencies=artifacts.color_frequencies or [],
            material_quantization_assessment=get_material_quantization_assessment(),
        )
        mapped_colors = ColorInventoryModel.build(
            [
                entry.with_palette_mapping(
                    palette_id=semantic_color.mapped_palette_id or "palette-achromatic-1",
                    tone=semantic_color.mapped_tone or 0,
                    tone_rgb=semantic_color.mapped_tone_rgb or entry.rgb,
                    tone_distance=semantic_color.mapped_tone_distance or 0.0,
                )
                if (semantic_color := next((item for item in palette_analysis.semantic_colors if item.color_id == entry.color_id), None))
                and semantic_color.mapped_palette_id is not None
                else entry
                for entry in colors_inventory
            ]
        )
        graph = InventoryGraphModel.build(
            elements=elements_inventory,
            styles=styles_inventory,
            colors=mapped_colors,
            palettes=tuple(palette_analysis.core_palettes),
        )
        token_inventory = build_token_inventory(graph, palette_analysis)
        validated_inventory = apply_token_rules(
            token_inventory,
            InventoryGraphModel.build(
                elements=graph.elements,
                styles=graph.styles,
                colors=graph.colors,
                palettes=graph.palettes,
                tokens=token_inventory,
            ),
        )

        self.assertGreater(len(token_inventory), 0)
        self.assertTrue(any(token.path_string.startswith("glow.color.") for token in token_inventory))
        self.assertTrue(any(token.is_semantic or token.is_component for token in token_inventory))
        self.assertEqual(len(validated_inventory), len(token_inventory))
        self.assertTrue(
            any(token.validations for token in validated_inventory if token.is_semantic)
        )

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
        self.assertIn("color_processing", results)
        self.assertIn("token_processing", results)
        self.assertIn("accessibility", results)
        self.assertIn("effect_colors", results)
        self.assertEqual(results["color_processing"]["artifact"], "color_scheme.json")
        self.assertEqual(results["accessibility"]["contrast"]["artifact"], "contrast_report_original.json")
        self.assertEqual(results["effect_colors"]["artifact"], "effect_colors_original.json")
        self.assertEqual(results["color_processing"]["palette_preview_artifact"], "palette_preview.png")
        self.assertEqual(results["color_processing"]["palette_preview_output"], "palette_preview.png")
        self.assertEqual(results["color_processing"]["palette_preview_location"], "artifacts")
        self.assertEqual(results["token_processing"]["artifact"], "tokens_original.json")
        self.assertEqual(results["token_processing"]["graph_artifact"], "inventory_graph.json")
        preview_output = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / results["color_processing"]["palette_preview_output"]
        )
        self.assertTrue(preview_output.exists())
        self.assertEqual(results["render_snapshot"]["artifact"], "render_snapshot_original.json")
        css_overview_path = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / "css_overview_original.json"
        )
        self.assertTrue(css_overview_path.exists())
        css_overview_payload = json.loads(css_overview_path.read_text(encoding="utf-8"))
        self.assertIn("colors", css_overview_payload)
        self.assertIn("contrast_issues", css_overview_payload)
        self.assertIn("unused_declarations", css_overview_payload)
        self.assertTrue(
            all(
                "color_id" in entry or not entry
                for entries in css_overview_payload["colors"].values()
                for entry in entries
            )
        )
        colors_inventory_path = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / "colors_inventory_original.json"
        )
        self.assertTrue(colors_inventory_path.exists())
        colors_inventory_payload = json.loads(colors_inventory_path.read_text(encoding="utf-8"))
        self.assertIn("entries", colors_inventory_payload)
        self.assertTrue(
            any(
                entry.get("mapped_palette_id") is not None
                or entry.get("display_pixel_count", 0) > 0
                for entry in colors_inventory_payload["entries"]
            )
        )
        self.assertTrue(
            any(
                entry.get("observed_usage_count", 0) > 0
                and entry.get("observed_roles")
                for entry in colors_inventory_payload["entries"]
            )
        )
        contrast_report_path = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / "contrast_report_original.json"
        )
        self.assertTrue(contrast_report_path.exists())
        contrast_report_payload = json.loads(contrast_report_path.read_text(encoding="utf-8"))
        self.assertIn("issues", contrast_report_payload)
        if contrast_report_payload["issues"]:
            self.assertTrue(
                any(
                    issue.get("element_id")
                    and issue.get("foreground", {}).get("color_id")
                    for issue in contrast_report_payload["issues"]
                )
            )
        effect_colors_path = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / "effect_colors_original.json"
        )
        self.assertTrue(effect_colors_path.exists())
        effect_colors_payload = json.loads(effect_colors_path.read_text(encoding="utf-8"))
        self.assertIn("entries", effect_colors_payload)
        self.assertIn("by_property", effect_colors_payload)
        tokens_path = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / "tokens_original.json"
        )
        inventory_graph_path = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / "inventory_graph.json"
        )
        self.assertTrue(tokens_path.exists())
        self.assertTrue(inventory_graph_path.exists())
        tokens_payload = json.loads(tokens_path.read_text(encoding="utf-8"))
        self.assertIn("glow", tokens_payload)
        self.assertIn("color", tokens_payload["glow"])
        graph_payload = json.loads(inventory_graph_path.read_text(encoding="utf-8"))
        self.assertIn("summary", graph_payload)
        self.assertIn("tokens", graph_payload)
        self.assertIn("relations", graph_payload)
        self.assertIn("css_overview", graph_payload)
        self.assertIn("contrast_report", graph_payload)
        self.assertIn("effect_color_report", graph_payload)
        self.assertIn("color_scheme", graph_payload)
        self.assertIn("pixel_frequencies_display", graph_payload)
        self.assertIn("element_visual_context", graph_payload["relations"])
        self.assertIn("element_adjacency", graph_payload["relations"])
        self.assertGreater(graph_payload["summary"]["element_count"], 0)
        self.assertGreaterEqual(
            graph_payload["summary"]["visible_element_count"],
            graph_payload["summary"]["text_element_count"],
        )
        self.assertGreaterEqual(graph_payload["summary"]["color_count"], 1)
        self.assertGreaterEqual(graph_payload["summary"]["pixel_count"], 1)
        self.assertEqual(
            graph_payload["summary"]["contrast_issue_count"],
            len(graph_payload["contrast_report"]["issues"]),
        )
        self.assertEqual(
            graph_payload["summary"]["unused_declaration_count"],
            graph_payload["css_overview"]["unused_declarations"]["count"],
        )
        self.assertEqual(
            graph_payload["summary"]["display_pixel_count"],
            graph_payload["pixel_frequencies_display"]["total_pixels_considered"],
        )

    def test_run_pipeline_preserves_zip_project_skeleton_in_output(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "Pagina/menu.html",
                "<html><body style=\"background:#000;color:#fff\"><h1>Hola</h1></body></html>",
            )
            archive.writestr("Pagina/css/site.css", "body { margin: 0; }")

        app = create_app()
        upload = InMemoryUpload("Pagina_de_prueba_2.zip", buffer.getvalue())
        with app.test_request_context("/results", method="POST"):
            results, error = run_pipeline(upload)

        self.assertIsNone(error)
        assert results is not None
        session_dir = Path("workspace/sessions") / results["session_dirname"]
        self.assertTrue((session_dir / "input" / "Pagina" / "menu.html").exists())
        self.assertTrue((session_dir / "output" / "Pagina" / "menu.html").exists())
        self.assertTrue((session_dir / "output" / "Pagina" / "css" / "site.css").exists())
        self.assertFalse((session_dir / "output" / "palette_preview.png").exists())
        self.assertFalse((session_dir / "output" / "Pagina_de_prueba_2.zip").exists())
        self.assertTrue((session_dir / "artifacts" / "palette_preview.png").exists())
        self.assertTrue((session_dir / "artifacts" / "Pagina_de_prueba_2.zip").exists())

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
            Path("engine/domain/models/color.py"),
            Path("engine/domain/models/palette.py"),
            Path("engine/domain/models/snapshot.py"),
            Path("engine/domain/models/environmental_assessment/energy_consumption.py"),
            Path("engine/domain/models/environmental_assessment/carbon_footprint.py"),
            Path("engine/domain/data/web_colors.py"),
            Path("engine/domain/enums/scope/css_properties.py"),
            Path("engine/domain/enums/scope/html_elements.py"),
            Path("engine/domain/enums/scope/json_exports.py"),
            Path("engine/domain/enums/types/style.py"),
            Path("engine/domain/enums/types/color.py"),
            Path("engine/domain/enums/types/elements.py"),
            Path("engine/domain/enums/types/transformations.py"),
            Path("engine/adapters/file_system/file_handler.py"),
            Path("engine/adapters/file_system/code_processor.py"),
            Path("engine/adapters/browser/snapshot_analyzer.py"),
            Path("engine/adapters/browser/prototype_renderer.py"),
            Path("engine/adapters/utils/io.py"),
            Path("engine/adapters/utils/screenshot.py"),
            Path("engine/validators/file_handling"),
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
            Path("engine/models/debug_trace.py"),
            Path("engine/models/pipeline_context.py"),
            Path("engine/models/color_processing"),
            Path("engine/models/environmental_assessment"),
            Path("engine/models/prototype_structural_extractor"),
            Path("engine/models/recommendations"),
            Path("engine/services/file_handling"),
            Path("engine/services/color_processing"),
            Path("engine/services/environmental_assessment"),
            Path("engine/services/prototype_structural_extractor"),
            Path("engine/services/transformation"),
            Path("engine/enums/core"),
            Path("engine/enums/scope"),
            Path("engine/utils"),
            Path("engine/services/color_service.py"),
            Path("engine/services/debug_trace_service.py"),
            Path("engine/services/results_compiler_service.py"),
            Path("engine/services/file_handling/asset_staging_service.py"),
            Path("engine/services/file_handling/artifact_storage_service.py"),
        )
        for path in removed_paths:
            self.assertFalse(path.exists(), msg=str(path))

    def test_legacy_wrapper_symbols_are_removed(self) -> None:
        self.assertFalse(
            Path("engine/services/prototype_structural_extractor/page_capture_service.py").exists()
        )
        self.assertFalse(Path("engine/transformation/transformations_pipeline.py").exists())
        self.assertFalse(Path("engine/file_handling/project_intake_pipeline.py").exists())
        self.assertFalse(Path("engine/environmental_assessment/environmental_assessment_pipeline.py").exists())
        self.assertFalse(Path("engine/prototype_structural_extractor/prototype_state_pipeline.py").exists())

    def test_wrapper_package_inits_are_removed(self) -> None:
        removed_inits = (
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

    def test_nested_stage_directories_are_removed(self) -> None:
        removed_stage_dirs = (
            Path("engine/pipeline/stages/color_processing"),
            Path("engine/pipeline/stages/environmental_assessment"),
            Path("engine/pipeline/stages/file_handling"),
            Path("engine/pipeline/stages/prototype_structural_extractor"),
            Path("engine/pipeline/stages/recommendations"),
            Path("engine/pipeline/stages/results"),
            Path("engine/pipeline/stages/transformation"),
        )
        for path in removed_stage_dirs:
            self.assertFalse(path.exists(), msg=str(path))

    def test_pixel_frequency_service_only_keeps_domain_entrypoints(self) -> None:
        self.assertFalse(Path("engine/services/color_processing/pixel_frequency_service.py").exists())
        content = Path("engine/adapters/utils/screenshot.py").read_text(encoding="utf-8")
        self.assertNotIn("def json_default_numpy_serializer(", content)

    def test_results_view_model_is_precomputed_in_python(self) -> None:
        results = {
            "carbon_footprint": 697.5,
            "environmental_co2eq_per_use": 654.45,
            "color_processing": {
                "named_color_breakdown": [
                    {
                        "display_name": "WhiteSmoke",
                        "family": "Neutral",
                        "hex_value": "#f5f5f5",
                        "percentage": 26.63,
                    },
                    {
                        "display_name": "Red",
                        "family": "Red",
                        "hex_value": "#ff0000",
                        "percentage": 23.70,
                    },
                    {
                        "display_name": "Violet",
                        "family": "Violet",
                        "hex_value": "#ee82ee",
                        "percentage": 9.35,
                    },
                    {
                        "display_name": "MediumOrchid",
                        "family": "Violet",
                        "hex_value": "#ba55d3",
                        "percentage": 8.90,
                    },
                ],
                "core_palettes": {
                    "achromatic_palette": {
                        "display_name": "Neutral",
                        "tones": [{"tone": 0, "hex_value": "#000000"}],
                    },
                    "chromatic_palettes": [
                        {
                            "display_name": "Violet",
                            "tones": [{"tone": 50, "hex_value": "#9b5dbb"}],
                        },
                        {
                            "display_name": "Red",
                            "tones": [{"tone": 50, "hex_value": "#ef0000"}],
                        },
                    ],
                },
            },
        }

        view = _build_results_view(results)

        self.assertAlmostEqual(view["initial_reduction"], 43.05)
        self.assertEqual(view["dominant_color_count"], 3)
        self.assertEqual(view["dominant_rows"][0]["label"], "Neutral")
        self.assertEqual(view["dominant_rows"][1]["label"], "Red")
        self.assertEqual(view["dominant_rows"][2]["label"], "Violet")
        self.assertAlmostEqual(view["dominant_rows"][2]["percentage"], 18.25)
        self.assertEqual(len(view["palette_rows"]), 3)
        self.assertEqual(view["palette_rows"][0]["label"], "Neutral")

    def test_results_template_no_longer_contains_macro_preparation_block(self) -> None:
        template = Path("app/templates/results.html").read_text(encoding="utf-8")

        self.assertNotIn("{% macro broad_family", template)
        self.assertNotIn("dominant_rows = namespace", template)
        self.assertNotIn("top_three = namespace", template)
        self.assertNotIn("core_palettes = color_processing.core_palettes", template)
        self.assertIn("Contrast report", template)
        self.assertIn("Effect color evidence", template)


if __name__ == "__main__":
    unittest.main()
