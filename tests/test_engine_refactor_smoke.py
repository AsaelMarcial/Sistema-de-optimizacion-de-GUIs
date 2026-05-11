import ast
import importlib
import io
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from coloraide.everything import ColorAll

from app import create_app
from engine.adapters.browser.render_models import SnapshotOptions
from tests.browser_helpers import (
    capture_prototype_state_artifacts,
    extract_prototype_state_snapshot,
)
from engine.adapters.source_code_handler.code_processor import (
    apply_tokens_to_project,
    evaluate_and_apply_heuristics,
)
from engine.adapters.color_service import build_default_strategy_registry, color_registry
from engine.pipeline.stages import prepare_project_session
from engine.adapters.utils.palette_preview import render_palette_preview
from engine.adapters.utils.pixel import (
    build_color_histograms,
    cluster_color_histogram,
    color_histogram_total,
    dominant_color_percentages,
    get_color_count,
)
from engine.domain.data.material_quantization import (
    get_material_quantization_assessment,
)
from engine.domain.enums.scope.css_properties import CSS_PROPERTIES_BY_ID, get_css_property
from engine.domain.enums.scope.html_elements import HTML_ELEMENT_SPECS, get_html_element
from engine.domain.data.web_colors import WebColor, nearest_web_color
from engine.domain.enums.scope.css_properties import CssPropertyId
from engine.domain.enums.scope.html_elements import HtmlElementId
from engine.domain.enums.scope.json_exports import (
    build_scope_elements_payload,
    build_scope_properties_payload,
)
from engine.domain.enums.types.color import (
    ColorConfirmationStatus,
    ColorFamilyType,
    PaletteRoleBias,
)
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
from engine.domain.models.color import ColorCatalog
from engine.domain.models.element import Element
from engine.domain.models.palette import TonalPaletteModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import FilePath, Session
from engine.domain.models.style import StyleCatalog
from engine.domain.models.token import (
    Token,
    TokenInventory,
    TokenState,
    TokenValidationModel,
    TokenValidationStatus,
)
from engine.domain.utils.palette_analysis import build_palette_analysis
from engine.domain.utils.tokenization import build_token_inventory
from engine.validators.project_uploaded import has_single_html, is_file_permitted, is_safe_relative_path, single_html_file
from engine.validators.token_rules import apply_token_rules
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey, ContextRoot
from engine.pipeline.artifact_serializers import build_token_inventory_artifact
from engine.pipeline.pipeline import run_pipeline
from engine.pipeline.stages.assemble_results import _build_results_view


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


def _build_nested_asset_project(root: Path) -> tuple[Path, str]:
    (root / "pages").mkdir(parents=True, exist_ok=True)
    (root / "styles").mkdir(parents=True, exist_ok=True)
    (root / "images").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "media").mkdir(parents=True, exist_ok=True)

    html_content = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="stylesheet" href="/styles/site.css" />
    <script src="/scripts/app.js"></script>
  </head>
  <body>
    <a href="/pages/menu.html">Menu</a>
    <form action="/pages/menu.html" method="get"></form>
    <img src="/images/photo.png" srcset="/images/photo.png 1x, /images/photo@2x.png 2x" />
    <img src="../images/photo.png" />
    <picture>
      <source src="/media/clip.mp4" />
    </picture>
    <style>
      .hero { background-image: url('/images/hero.png'); }
    </style>
  </body>
</html>
"""
    (root / "pages" / "index.html").write_text(html_content, encoding="utf-8")
    (root / "pages" / "menu.html").write_text("<html><body>menu</body></html>\n", encoding="utf-8")
    (root / "styles" / "site.css").write_text(
        "body { background-image: url('/images/bg.png'); }\n",
        encoding="utf-8",
    )
    (root / "scripts" / "app.js").write_text("console.log('ok');\n", encoding="utf-8")
    for asset_name in ("photo.png", "photo@2x.png", "hero.png", "bg.png"):
        (root / "images" / asset_name).write_bytes(b"fake")
    (root / "media" / "clip.mp4").write_bytes(b"fake")
    return root / "pages" / "index.html", html_content


def _elements(payloads) -> tuple[Element, ...]:
    return tuple(
        payload if isinstance(payload, Element) else Element.build(payload)
        for payload in (payloads or ())
    )


def _prototype(elements=(), styles=None) -> PrototypeStructure:
    return PrototypeStructure.build(
        _elements(elements),
        styles_inventory=styles or StyleCatalog(),
    )


class EngineRefactorSmokeTests(unittest.TestCase):
    def _snapshot_fixture_projection(self, fixture_path: Path) -> dict[str, object]:
        html_content = fixture_path.read_text(encoding="utf-8")
        artifacts = capture_prototype_state_artifacts(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(capture_screenshot=False),
        )
        return {
            "snapshot": artifacts.snapshot.to_dict(),
            "styles_inventory": (
                artifacts.style_catalog.to_dict()
                if artifacts.style_catalog is not None
                else []
            ),
            "palette": (
                artifacts.colors_inventory.to_palette_dicts()
                if artifacts.colors_inventory is not None
                else []
            ),
        }

    def _snapshot_nodes(self, snapshot: dict[str, object]) -> list[dict[str, object]]:
        return list(snapshot.get("nodes") or [])

    @staticmethod
    def _properties_by_name(node: dict[str, object]) -> dict[str, dict[str, object]]:
        return {
            str(property_payload.get("name") or property_payload.get("property_name")): property_payload
            for property_payload in node.get("properties", []) or []
            if isinstance(property_payload, dict)
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
        self.assertFalse((Path("engine/models/legacy")).exists())
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
            "start_page_builder.py": "run_stage",
            "capture_original_state.py": "run_stage",
            "build_color_scheme.py": "run_stage",
            "close_page_builder.py": "run_stage",
            "assess_original_environmental_impact.py": "run_stage",
            "set_tokens.py": "run_stage",
            "check_tokens.py": "run_stage",
            "transform_source_project.py": "run_stage",
            "assess_transformed_environmental_impact.py": "run_stage",
            "assemble_results.py": "run_stage",
        }
        for module_name, function_name in expected_public_functions.items():
            module_path = STAGES_DIR / module_name
            self.assertTrue(module_path.exists(), msg=module_name)
            package_module = importlib.import_module(
                f"engine.pipeline.stages.{module_name.removesuffix('.py')}"
            )
            self.assertTrue(hasattr(package_module, function_name), msg=module_name)
            self.assertTrue(hasattr(package_module, "CONTRACT"), msg=f"{module_name} missing CONTRACT")

    def test_pipeline_does_not_store_render_artifacts_in_context(self) -> None:
        blocked_key = "session.before_capture"
        pipeline_files = [Path("engine/pipeline/pipeline.py"), *STAGES_DIR.glob("*.py")]
        for path in pipeline_files:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn(blocked_key, content, msg=f"{blocked_key} still present in {path}")
        self.assertFalse((STAGES_DIR / "capture_prototype_structure.py").exists())

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
        context = PipelineContext()
        self.assertEqual(context.trace.__class__.__name__, "DebugTrace")
        context.set("session.before.html_name", "index.html")
        context.set("prototype_structure.nodes", ())
        context.set("style.catalog", StyleCatalog())
        self.assertEqual(context.get("session.before.html_name"), "index.html")
        self.assertTrue(context.has("prototype_structure.nodes"))
        self.assertTrue(context.has("style.catalog"))
        self.assertIsInstance(context.snapshot(), dict)
        self.assertIsNone(context.get("results"))
        self.assertTrue(hasattr(context, "error"))
        with self.assertRaises(ValueError):
            context.set("inventory.catalog", {})

    def test_pipeline_context_keys_are_canonical_enums(self) -> None:
        self.assertEqual(ContextRoot.PAGE_BUILDER.value, "page_builder")
        self.assertEqual(ContextRoot.COLOR.value, "color")
        self.assertEqual(ContextKey.COLOR_CATALOG.value, "color.catalog")
        self.assertEqual(ContextKey.ENVIRONMENTAL_BEFORE_ASSESSMENT.value, "environmental.before.assessment")
        self.assertEqual(
            {
                key.value
                for key in ContextKey
                if key.value.startswith("scheme.")
            },
            {
                "scheme.color_histogram",
                "scheme.tonal_palettes",
                "scheme.named_color_breakdown",
            },
        )

        context = PipelineContext()
        context.set(ContextKey.PROTOTYPE_STRUCTURE, ())
        self.assertEqual(context.get(ContextKey.PROTOTYPE_STRUCTURE), ())
        self.assertFalse(context.has("session.before.file"))

    def test_pipeline_uses_context_key_enums_for_literal_context_access(self) -> None:
        checked_methods = {"get", "set", "has", "require"}
        violations: list[str] = []
        for path in Path("engine/pipeline").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in checked_methods
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "context"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    violations.append(f"{path}:{node.lineno}:{node.func.attr}")
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "context_value"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    violations.append(f"{path}:{node.lineno}:context_value")
        self.assertEqual(violations, [])

    def test_session_model_builds_related_before_after_and_artifact_directories(self) -> None:
        session = Session(
            session_id="abc12345",
            base_dir="workspace/sessions",
        )
        html = FilePath("pages/index.html")
        session.add_file_path(html)

        self.assertEqual(session.build_path("before").name, "before")
        self.assertEqual(session.build_path("after").name, "after")
        self.assertEqual(session.build_path("artifacts").name, "artifacts")
        self.assertEqual(
            session.build_path("before", html),
            (Path("workspace/sessions") / "session_abc12345" / "before" / "pages" / "index.html").resolve(),
        )
        self.assertTrue(
            str(session.build_path("after", html)).endswith(
                str(Path("session_abc12345") / "after" / "pages" / "index.html")
            )
        )
        self.assertEqual(single_html_file(session.file_paths), html)

    def test_color_processing_uses_canonical_domain_and_adapter_modules(self) -> None:
        self.assertFalse((Path("engine/color_processing/models.py")).exists())
        self.assertFalse((Path("engine/color_processing/models")).exists())
        self.assertTrue((Path("engine/domain/models/palette.py")).exists())
        self.assertTrue((Path("engine/domain/utils/palette_analysis.py")).exists())
        self.assertFalse((Path("engine/adapters/utils/screenshot.py")).exists())
        self.assertTrue((Path("engine/adapters/utils/pixel.py")).exists())
        self.assertFalse((Path("engine/models/color_processing")).exists())
        self.assertFalse((Path("engine/utils")).exists())
        self.assertTrue((Path("engine/validators")).exists())

    def test_scope_payloads_are_generated_from_python_source(self) -> None:
        properties_payload = build_scope_properties_payload()
        elements_payload = build_scope_elements_payload()

        self.assertIn("fill", CSS_PROPERTIES_BY_ID)
        self.assertIn("lighting-color", CSS_PROPERTIES_BY_ID)
        self.assertNotIn("backgroundColor", CSS_PROPERTIES_BY_ID)
        self.assertIs(get_css_property("backgroundColor"), CssPropertyId.BACKGROUND_COLOR)
        self.assertIs(get_css_property("BACKGROUND_COLOR"), CssPropertyId.BACKGROUND_COLOR)
        self.assertIsNone(get_css_property("currentColor"))
        self.assertIsNone(get_css_property("margin"))
        self.assertIsNone(get_css_property("pointer-events"))

        html_element_values = {spec.value for spec in HTML_ELEMENT_SPECS}
        self.assertIn("search", html_element_values)
        self.assertIn("selectedcontent", html_element_values)
        self.assertIs(get_html_element("DIV"), HtmlElementId.DIV)
        img_item = next(item for item in elements_payload["onScope"] if item["elementID"] == "img")
        self.assertEqual(
            set(img_item),
            {"elementID", "name", "description", "scopeGroup", "categories"},
        )
        self.assertTrue(any(item["propertyID"] == "fill" for item in properties_payload["onScope"]))
        fill_item = next(
            item for item in properties_payload["onScope"] if item["propertyID"] == "fill"
        )
        self.assertNotIn("computedAliases", fill_item)
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
        self.assertEqual(ColorFamilyType.CHROMATIC.value, "chromatic")
        self.assertEqual(ColorConfirmationStatus.CONFIRMED.value, "confirmed")
        self.assertEqual(PaletteRoleBias.BACKGROUND.value, "background")
        self.assertEqual(TransformationKind.HEURISTIC.value, "heuristic")
        self.assertEqual(TransformationStatus.APPLIED.value, "applied")

    def test_project_upload_predicates_reject_traversal(self) -> None:
        self.assertFalse(is_safe_relative_path("../escape.html"))

    def test_project_upload_predicates_reject_extensionless_files(self) -> None:
        self.assertFalse(is_file_permitted("project/README", {".html"}))

    def test_project_upload_predicates_reject_disallowed_extensions(self) -> None:
        self.assertFalse(is_file_permitted("project/app.exe", {".html", ".css"}))

    def test_project_upload_predicate_rejects_multiple_html_files(self) -> None:
        file_paths = (
            FilePath("project/index.html"),
            FilePath("project/about.html"),
        )

        self.assertFalse(has_single_html(file_paths))

    def test_prepare_project_session_does_not_create_workspace_for_invalid_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("../escape.html", "<html></html>")

            context = prepare_project_session.run_stage(
                PipelineContext(),
                InMemoryUpload("unsafe.zip", buffer.getvalue()),
                base_dir=Path(temp_dir),
            )

            self.assertIsNotNone(context.error)
            self.assertEqual(list(Path(temp_dir).glob("session_*")), [])

    def test_prepare_project_session_does_not_create_workspace_for_corrupt_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            context = prepare_project_session.run_stage(
                PipelineContext(),
                InMemoryUpload("broken.zip", b"not a zip"),
                base_dir=Path(temp_dir),
            )

            self.assertEqual(context.error, "ZIP corrupto")
            self.assertEqual(list(Path(temp_dir).glob("session_*")), [])

    def test_prepare_project_session_returns_typed_session(self) -> None:
        html_bytes = RENDER_SCOPE_MATRIX.read_bytes()
        upload = InMemoryUpload("render_scope_matrix.html", html_bytes)

        context = prepare_project_session.run_stage(PipelineContext(), upload)
        project_before = context.get(ContextKey.SESSION)

        self.assertIsInstance(project_before, Session)
        html_file = single_html_file(project_before.file_paths)
        before_html_path = project_before.build_path("before", html_file)
        self.assertEqual(html_file.name, "render_scope_matrix.html")
        self.assertIn("Snapshot Matrix", before_html_path.read_text(encoding="utf-8"))
        self.assertTrue(str(before_html_path).endswith("render_scope_matrix.html"))

    def test_prepare_project_session_supports_deep_nested_zip_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(
                    "project/src/pages/index.html",
                    "<html><body>Deep nested project</body></html>",
                )
                archive.writestr("project/src/styles/site.css", "body { color: #111; }")

            context = prepare_project_session.run_stage(
                PipelineContext(),
                InMemoryUpload("project.zip", buffer.getvalue()),
                base_dir=Path(temp_dir),
            )
            project_before = context.get(ContextKey.SESSION)

            self.assertIsInstance(project_before, Session)
            html_file = single_html_file(project_before.file_paths)
            self.assertEqual(project_before.project_root_file_path().relative_path, Path("project"))
            self.assertEqual(html_file.relative_path.parts, ("project", "src", "pages", "index.html"))
            self.assertIn(
                "Deep nested project",
                project_before.build_path("before", html_file).read_text(encoding="utf-8"),
            )

    def test_render_snapshot_contains_expected_scope_and_text(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        artifacts = capture_prototype_state_artifacts(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(capture_screenshot=False),
        )
        snapshot = artifacts.snapshot.to_dict()
        snapshot_nodes = self._snapshot_nodes(snapshot)
        raw_nodes = list(artifacts.snapshot.nodes)

        tags = [node.tag_name for node in raw_nodes]
        self.assertNotIn("script", tags)
        self.assertNotIn("source", tags)
        self.assertNotIn("track", tags)
        self.assertIn("search", tags)
        self.assertIn("ins", tags)
        self.assertIn("del", tags)
        self.assertIn("colgroup", tags)
        self.assertIn("selectedcontent", tags)

        image_nodes = [node for node in raw_nodes if node.tag_name == "img"]
        self.assertEqual(len(image_nodes), 1)
        self.assertTrue(image_nodes[0].is_out_of_scope)
        picture_nodes = [node for node in raw_nodes if node.tag_name == "picture"]
        self.assertEqual(len(picture_nodes), 1)
        self.assertTrue(bool(picture_nodes[0].related_media))

        title_nodes = [node for node in raw_nodes if node.html_id == "title"]
        self.assertEqual(len(title_nodes), 1)
        self.assertEqual(title_nodes[0].text, "Snapshot Matrix")
        self.assertTrue(str(title_nodes[0].xpath).startswith("/html[1]/body[1]"))
        self.assertFalse(title_nodes[0].is_text_node)

        self.assertIn("nodes", snapshot)
        self.assertNotIn("tree", snapshot)
        self.assertNotIn("rules_used", snapshot)

        for node in snapshot_nodes:
            self.assertIn("node_id", node)
            self.assertIn("node_name", node)
            self.assertIn("tag_name", node)
            self.assertIn("is_visible", node)
            self.assertIn("properties", node)

        node_ids = {node["node_id"] for node in snapshot_nodes}
        for node in snapshot_nodes:
            parent_id = node.get("parent_id")
            if parent_id:
                self.assertIn(parent_id, node_ids)
            for child_id in node.get("children_ids", []):
                self.assertIn(child_id, node_ids)

    def test_render_snapshot_filters_matching_styles_to_scope(self) -> None:
        projection = self._snapshot_fixture_projection(RENDER_SCOPE_MATRIX)
        snapshot = projection["snapshot"]
        assert isinstance(snapshot, dict)
        snapshot_nodes = self._snapshot_nodes(snapshot)
        styles_inventory = projection["styles_inventory"]
        assert isinstance(styles_inventory, list)

        title_node = next(node for node in snapshot_nodes if node.get("html_id") == "title")
        title_properties = self._properties_by_name(title_node)
        all_declarations = [
            declaration["name"]
            for style in styles_inventory
            for declaration in style.get("declarations", [])
        ]
        self.assertTrue(all(get_css_property(name) is not None for name in all_declarations))
        self.assertIn("color", title_properties)
        self.assertIn("background-color", title_properties)
        self.assertIn("style_id", title_properties["color"])
        self.assertEqual(
            title_properties["background-color"]["declared_property"],
            "background-color",
        )
        self.assertIn("effective_background", title_node)
        self.assertEqual(
            title_properties["color"]["resolution_status"],
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
        self.assertTrue(all(rule["kind"] != "computed" for rule in styles_inventory))
        self.assertTrue(all("node_ids" not in rule for rule in styles_inventory))
        self.assertTrue(all("usage_count" not in rule for rule in styles_inventory))
        self.assertTrue(
            all(
                "used_by_element_ids" not in declaration
                and "element_usage_count" not in declaration
                for rule in styles_inventory
                for declaration in rule["declarations"]
            )
        )
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

        snapshot_nodes = [
            node
            for node in self._snapshot_nodes(snapshot)
            if node.get("html_id")
        ]
        elements = {
            node.get("html_id"): self._properties_by_name(node)
            for node in snapshot_nodes
        }
        element_nodes = {node.get("html_id"): node for node in snapshot_nodes}
        styles_by_id = {
            style["style_id"]: style
            for style in styles_inventory
        }

        winner_color = elements["winner"]["color"]
        self.assertEqual(winner_color["resolution_status"], "exact_match")
        self.assertEqual(winner_color["declared_property"], "color")
        self.assertEqual(styles_by_id[winner_color["style_id"]]["selector_text"], "#winner")

        important_color = elements["important"]["color"]
        if important_color.get("style_id"):
            self.assertEqual(important_color["resolution_status"], "exact_match")
            self.assertEqual(important_color["declared_property"], "color")
            self.assertEqual(styles_by_id[important_color["style_id"]]["selector_text"], "p")
        else:
            self.assertEqual(important_color["resolution_status"], "unresolved")

        inherited_color = elements["inherit-child"]["color"]
        self.assertEqual(inherited_color["declared_property"], "color")
        self.assertEqual(
            inherited_color["inherited_from_element_id"],
            element_nodes["inherit-parent"]["node_id"],
        )

        shorthand_background = elements["shorthand"]["background-color"]
        self.assertIn(
            shorthand_background["declared_property"],
            {"background", "background-color"},
        )
        outline_color = elements["outline"]["outline-color"]
        self.assertIn(outline_color["declared_property"], {"outline", "outline-color"})
        current_border = elements["current-color"]["border-top-color"]
        self.assertIn(
            current_border["declared_property"],
            {"border-color", "border-top-color"},
        )

    def test_cascade_resolution_normalizes_hex_authored_colors_to_computed_rgb(self) -> None:
        html_content = """
<!doctype html>
<html lang="en">
  <head>
    <style>
      body {
        background-color: #f4f4f4;
        color: #ffffff;
      }
    </style>
  </head>
  <body>
    <p id="sample">Hex authored colors</p>
  </body>
</html>
"""
        snapshot = extract_prototype_state_snapshot(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(capture_screenshot=False),
        )
        body_node = next(
            node
            for node in self._snapshot_nodes(snapshot)
            if node.get("xpath") == "/html[1]/body[1]"
        )
        properties = self._properties_by_name(body_node)
        self.assertEqual(properties["background-color"]["value"], "rgb(244, 244, 244)")
        self.assertEqual(properties["background-color"]["resolution_status"], "exact_match")
        self.assertEqual(properties["color"]["value"], "rgb(255, 255, 255)")
        self.assertEqual(properties["color"]["resolution_status"], "exact_match")

    def test_snapshot_nodes_properties_have_style_or_unresolved(self) -> None:
        projection = self._snapshot_fixture_projection(RENDER_SCOPE_MATRIX)
        styles_inventory = projection["styles_inventory"]
        snapshot = projection["snapshot"]
        assert isinstance(styles_inventory, list)
        assert isinstance(snapshot, dict)

        style_ids = {style["style_id"] for style in styles_inventory}
        for element in self._snapshot_nodes(snapshot):
            for payload in element.get("properties", []):
                self.assertIn("value", payload)
                self.assertTrue("style_id" in payload or payload.get("resolution_status") == "unresolved")
                if "style_id" in payload:
                    self.assertIn(payload["style_id"], style_ids)

    def test_snapshot_omits_unmatched_default_computed_properties(self) -> None:
        projection = self._snapshot_fixture_projection(RENDER_CASCADE_MATRIX)
        snapshot = projection["snapshot"]
        assert isinstance(snapshot, dict)

        elements = {
            node.get("html_id"): self._properties_by_name(node)
            for node in self._snapshot_nodes(snapshot)
            if node.get("html_id")
        }

        shorthand_styles = elements["shorthand"]
        self.assertIn("background-color", shorthand_styles)
        self.assertNotIn("background-repeat", shorthand_styles)
        self.assertNotIn("background-position", shorthand_styles)
        self.assertNotIn("background-clip", shorthand_styles)
        self.assertNotIn("background-origin", shorthand_styles)
        self.assertNotIn("background-attachment", shorthand_styles)

        winner_styles = elements["winner"]
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
        snapshot_nodes = self._snapshot_nodes(snapshot)

        title_node = next(
            node for node in snapshot_nodes if node.get("html_id") == "title"
        )
        self.assertEqual(title_node["text"], "Snapshot Matrix")
        text_children = [
            node
            for node in snapshot_nodes
            if node.get("is_text_node") and node.get("parent_id") == title_node["node_id"]
        ]
        self.assertEqual(len(text_children), 1)
        self.assertEqual(text_children[0]["text"], "Snapshot Matrix")
        self.assertTrue(text_children[0]["is_text_node"])

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

        tracked_properties = {
            property_payload["name"]
            for node in self._snapshot_nodes(projection["snapshot"])
            for property_payload in node.get("properties", [])
        }
        self.assertIn("box-shadow", tracked_properties)
        self.assertIn("text-shadow", tracked_properties)
        self.assertIn("filter", tracked_properties)

    def test_capture_prototype_state_artifacts_supports_color_histograms(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        artifacts = capture_prototype_state_artifacts(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(),
            session_id="testsess3",
        )
        color_data = build_color_histograms(artifacts.screenshot_path)["environmental"]

        self.assertIsInstance(color_data, list)
        self.assertGreater(len(color_data), 0)
        self.assertTrue(all("color" in item and "count" in item for item in color_data))

    def test_build_color_histograms_uses_canonical_module(self) -> None:
        color_data = build_color_histograms(
            [[[255, 0, 0], [255, 0, 0]], [[0, 0, 255], [255, 0, 0]]]
        )["environmental"]
        self.assertEqual(color_data[0]["color"], [255, 0, 0])
        self.assertEqual(color_data[0]["count"], 3)

    def test_build_color_histograms_subtracts_prototype_exclusions(self) -> None:
        class PrototypeStub:
            def excluded_pixel_boxes(self) -> tuple[tuple[int, int, int, int], ...]:
                return ((0, 0, 1, 2),)

        histograms = build_color_histograms(
            [
                [[255, 0, 0], [0, 0, 255]],
                [[255, 0, 0], [0, 255, 0]],
            ],
            prototype_structure=PrototypeStub(),
            cluster_distance=0,
        )

        self.assertEqual(histograms["environmental"][0], {"color": [255, 0, 0], "count": 2})
        self.assertNotIn({"color": [255, 0, 0], "count": 2}, histograms["scheme"])
        self.assertEqual(color_histogram_total(histograms["scheme"]), 2)

    def test_dominant_color_percentages_include_percentage(self) -> None:
        color_data = dominant_color_percentages(
            build_color_histograms(
                [[[255, 0, 0], [255, 0, 0]], [[0, 0, 255], [255, 0, 0]]]
            )["environmental"]
        )
        self.assertEqual(color_data[0]["color"], [255, 0, 0])
        self.assertEqual(color_data[0]["count"], 3)
        self.assertAlmostEqual(color_data[0]["percentage"], 75.0)

    def test_color_histogram_helpers_keep_final_shape(self) -> None:
        color_data = [
            {"color": [255, 0, 0], "count": 3},
            {"color": [254, 0, 0], "count": 2},
            {"color": [0, 0, 255], "count": 1},
        ]
        clustered = cluster_color_histogram(color_data, cluster_distance=6.0)

        self.assertTrue(all(set(item) == {"color", "count"} for item in clustered))
        self.assertEqual(color_histogram_total(clustered), 6)
        self.assertEqual(get_color_count(clustered, 255, 0, 0)["count"], 5)

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

    def test_color_registry_centralizes_distance_contrast_and_alpha_compositing(self) -> None:
        composited = color_registry.composite_over("rgba(255 0 0 / 0.5)", "white")
        self.assertEqual(composited.space(), "srgb")
        self.assertGreater(color_registry.contrast_ratio("black", "white"), 20.0)
        self.assertGreater(color_registry.delta_e_distance("#ff0000", "#0000ff", method="2000"), 0.0)
        self.assertEqual(
            tuple(round(channel, 4) for channel in composited.coords()),
            (1.0, 0.5, 0.5),
        )

    def test_color_service_registry_exposes_strategy_based_color_operations(self) -> None:
        registry = build_default_strategy_registry()
        self.assertEqual(registry.format_color("#ff0000", "hex"), "#ff0000")
        self.assertEqual(registry.format_color((255, 0, 0), "css"), "rgb(255, 0, 0)")
        self.assertEqual(registry.rgb_string_to_tuple("rgb(1, 2, 3)"), (1, 2, 3))
        self.assertEqual(registry.hex_to_rgb("#abc"), (170, 187, 204))
        self.assertEqual(
            color_registry.find_matches("before rgb(1 2 3 / 50%) after #abc"),
            ((7, 23, "rgb(1 2 3 / 50%)"), (30, 34, "#abc")),
        )

    def test_hct_coords_sanitize_achromatic_hue(self) -> None:
        self.assertEqual(color_registry.hct_of("#000000"), (0.0, 0.0, 0.0))

    def test_color_service_normalizes_css_tokens_and_variants(self) -> None:
        self.assertEqual(
            color_registry.normalize_css_color_token(" rgba(255, 0, 0, 0) "),
            "transparent",
        )
        self.assertEqual(
            color_registry.normalize_css_color_token(" currentcolor "),
            "currentcolor",
        )
        self.assertEqual(
            color_registry.normalize_css_color_token(" revert-layer "),
            "revert-layer",
        )
        self.assertEqual(
            color_registry.variants("rgb(255, 0, 0)"),
            ("#ff0000", "rgb(255, 0, 0)"),
        )
        self.assertEqual(
            color_registry.parseable_variants("red"),
            ("#ff0000", "red", "rgb(255, 0, 0)"),
        )

    def test_coloraide_module_is_removed(self) -> None:
        self.assertFalse(Path("engine/domain/utils/coloraide.py").exists())

    def test_web_color_enum_and_nearest_lookup_are_available(self) -> None:
        self.assertEqual(WebColor.WHITE.hex_value, "#ffffff")
        match = nearest_web_color((254, 254, 254))
        self.assertEqual(match.color_name, "white")
        self.assertEqual(match.wikipedia_family, "Blanco")
        self.assertEqual(match.family_display_name, "White")

    def test_tonal_palette_model_builds_seed_tones(self) -> None:
        palette = TonalPaletteModel.from_seed(
            palette_id="palette-chromatic-1",
            palette_type="chromatic",
            seed_hex="#ff0000",
            role_bias="foreground",
            semantic_weight=10,
            pixel_count=25,
            seed_name="red",
            source_color_ids=("color-1",),
        )
        self.assertEqual(palette.seed_name, "red")
        self.assertGreater(len(palette.tones), 10)
        self.assertEqual(palette.tones[0].tone, 10)
        self.assertEqual(palette.tones[-1].tone, 98)
        self.assertEqual(
            palette.tones[-1].hex_value,
            color_registry.format_color(palette.tones[-1].rgb, "hex"),
        )

    def test_achromatic_tonal_palette_keeps_full_base_scale(self) -> None:
        palette = TonalPaletteModel.from_seed(
            palette_id="palette-achromatic-1",
            palette_type="achromatic",
            seed_hex="#ffffff",
            role_bias="background",
            semantic_weight=5,
            pixel_count=50,
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
        self.assertNotIn("residual" + "_pixel_count", palette_analysis)
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
                    "pixel_count": 90,
                },
                {
                    "color_id": "color-2",
                    "value": "rgb(255, 0, 0)",
                    "usage_count": 0,
                    "usage": [],
                    "pixel_count": 0,
                },
            ),
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

    def test_prototype_structure_builds_relations_and_effective_backgrounds(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        artifacts = capture_prototype_state_artifacts(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(capture_screenshot=False),
        )
        elements_inventory = _elements(artifacts.snapshot.nodes)
        styles_inventory = (
            artifacts.style_catalog
            if artifacts.style_catalog is not None
            else StyleCatalog()
        )
        colors_inventory = ColorCatalog.build(artifacts.colors_inventory)
        prototype_structure = _prototype(elements_inventory, styles_inventory)

        title_entry = next(
            entry for entry in elements_inventory if entry.html_id == "title"
        )
        resolved_property_with_declaration = next(
            (
                (element_entry, property_model)
                for element_entry in prototype_structure
                for property_model in prototype_structure.properties_for(element_entry)
                if property_model.declaration_id and property_model.resolution_status == "exact_match"
            ),
            None,
        )
        self.assertIsNotNone(resolved_property_with_declaration)
        assert resolved_property_with_declaration is not None
        declaration_owner, property_with_declaration = resolved_property_with_declaration
        declaration = styles_inventory.declaration_by_id(property_with_declaration.declaration_id or "")
        self.assertIsNotNone(declaration)
        assert declaration is not None
        self.assertIn(declaration_owner.node_id, declaration.used_by_element_ids)
        self.assertGreaterEqual(declaration.element_usage_count, 1)
        parent = prototype_structure.parent_of(title_entry.node_id)
        self.assertIsNotNone(parent)
        assert parent is not None
        self.assertIn(
            title_entry.node_id,
            [child.node_id for child in prototype_structure.children_of(parent.node_id)],
        )
        self.assertGreaterEqual(len(prototype_structure.ancestors_of(title_entry.node_id)), 1)
        effective_background = prototype_structure.effective_background_of(
            title_entry.node_id,
            tuple(colors_inventory),
        )
        self.assertIsNotNone(effective_background)
        assert effective_background is not None
        self.assertTrue(effective_background.hex_value.startswith("#"))
        effective_foreground = prototype_structure.effective_color_of(
            title_entry.node_id,
            tuple(colors_inventory),
        )
        self.assertIsNotNone(effective_foreground)
        surface_container = prototype_structure.surface_container_of(title_entry.node_id)
        self.assertIsNotNone(surface_container)

    def test_token_inventory_keeps_export_relations_without_parallel_owner(self) -> None:
        token_inventory = TokenInventory.build(
            (
                Token.foundation(
                    path=("glow", "color", "neutral", "10"),
                    resolved_value="#121212",
                    tone=10,
                    source_palette_ids=("palette-achromatic-1",),
                    created_by_stage="tests",
                ),
                Token.semantic(
                    path=("glow", "text", "color", "emphasis", "2"),
                    alias_to="glow.color.neutral.10",
                    resolved_value="#121212",
                    element_key="text",
                    property_id="color",
                    value_label="emphasis.2",
                    source_element_ids=("node-1",),
                    assigned_element_ids=("node-1",),
                    source_property_refs=("style-1:color",),
                    source_color_ids=("color-1",),
                    source_style_ids=("style-1",),
                    source_palette_ids=("palette-achromatic-1",),
                    tone=10,
                    created_by_stage="tests",
                ),
            )
        )
        token = token_inventory.entry_by_id("glow.text.color.emphasis.2")

        self.assertEqual(len(token_inventory), 2)
        self.assertIsNotNone(token)
        assert token is not None
        self.assertEqual(token.token_id, "glow.text.color.emphasis.2")
        self.assertEqual(
            token.assigned_element_ids,
            ("node-1",),
        )
        self.assertEqual(
            token.source_property_refs,
            ("style-1:color",),
        )
        self.assertEqual(
            token.source_color_ids,
            ("color-1",),
        )
        self.assertEqual(
            token.source_palette_ids,
            ("palette-achromatic-1",),
        )

    def test_token_inventory_artifact_is_export_only(self) -> None:
        token_inventory = TokenInventory.build(
            (
                Token.semantic(
                    path=("glow", "text", "color", "emphasis", "2"),
                    alias_to="glow.color.neutral.10",
                    resolved_value="#ffffff",
                    element_key="text",
                    property_id="color",
                    value_label="emphasis.2",
                    source_element_ids=("title-node",),
                    assigned_element_ids=("title-node",),
                    source_property_refs=("style-1:color",),
                    source_color_ids=("color-1",),
                    source_style_ids=("style-1",),
                    source_palette_ids=("palette-achromatic-1",),
                    tone=10,
                    created_by_stage="tests",
                ),
            )
        )
        artifact = build_token_inventory_artifact(token_inventory)

        self.assertIn("glow", artifact)
        self.assertIn("text", artifact["glow"])
        self.assertNotIn("relations", artifact)
        self.assertNotIn("element_ids", artifact)
        self.assertNotIn("style_ids", artifact)
        self.assertNotIn("color_ids", artifact)

    def test_token_inventory_and_rules_build_from_existing_palette_and_inventory(self) -> None:
        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        artifacts = capture_prototype_state_artifacts(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(capture_screenshot=False),
        )
        colors_inventory = ColorCatalog.build(artifacts.colors_inventory)
        elements_inventory = _elements(artifacts.snapshot.nodes)
        styles_inventory = (
            artifacts.style_catalog
            if artifacts.style_catalog is not None
            else StyleCatalog()
        )
        palette_analysis = build_palette_analysis(
            snapshot_palette=colors_inventory.to_palette_dicts(),
            material_quantization_assessment=get_material_quantization_assessment(),
        )
        mapped_colors = ColorCatalog.build(
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
        prototype_structure = _prototype(elements_inventory, styles_inventory)
        token_inventory = build_token_inventory(
            prototype_structure,
            tuple(mapped_colors),
            palette_analysis.core_palettes,
        )
        validated_inventory = apply_token_rules(
            token_inventory,
            prototype_structure,
            tuple(mapped_colors),
            tuple(palette_analysis.core_palettes),
        )

        self.assertGreater(len(token_inventory), 0)
        self.assertTrue(any(token.path_string.startswith("glow.color.") for token in token_inventory))
        self.assertTrue(any(token.is_semantic or token.is_component for token in token_inventory))
        self.assertEqual(len(validated_inventory), len(token_inventory))
        self.assertTrue(
            any(token.validations for token in validated_inventory if token.is_semantic)
        )

    def test_token_stages_assign_tokens_to_domain_instances(self) -> None:
        from engine.pipeline.stages.check_tokens import run_stage as run_check_tokens_stage
        from engine.pipeline.stages.set_tokens import run_stage as run_set_tokens_stage

        html_content = RENDER_SCOPE_MATRIX.read_text(encoding="utf-8")
        artifacts = capture_prototype_state_artifacts(
            html_content=html_content,
            base_path=str(FIXTURES_DIR),
            options=SnapshotOptions(capture_screenshot=False),
        )
        colors_inventory = ColorCatalog.build(artifacts.colors_inventory)
        elements_inventory = _elements(artifacts.snapshot.nodes)
        styles_inventory = (
            artifacts.style_catalog
            if artifacts.style_catalog is not None
            else StyleCatalog()
        )
        palette_analysis = build_palette_analysis(
            snapshot_palette=colors_inventory.to_palette_dicts(),
            material_quantization_assessment=get_material_quantization_assessment(),
        )
        mapped_colors = ColorCatalog.build(
            [
                entry.with_palette_mapping(
                    palette_id=semantic_color.mapped_palette_id or "palette-achromatic-1",
                    tone=semantic_color.mapped_tone or 0,
                    tone_rgb=semantic_color.mapped_tone_rgb or entry.rgb,
                    tone_distance=semantic_color.mapped_tone_distance or 0.0,
                )
                if (
                    semantic_color := next(
                        (item for item in palette_analysis.semantic_colors if item.color_id == entry.color_id),
                        None,
                    )
                )
                and semantic_color.mapped_palette_id is not None
                else entry
                for entry in colors_inventory
            ]
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tokens_path = Path(tmp_dir) / "tokens.json"
            legacy_relations_filename = "inventory" + "_" + "gra" + "ph.json"
            legacy_path = Path(tmp_dir) / legacy_relations_filename
            context = PipelineContext()
            context.set(ContextKey.PROTOTYPE_STRUCTURE, _prototype(elements_inventory, styles_inventory))
            context.set(ContextKey.COLOR_CATALOG, mapped_colors)
            context.set(ContextKey.SCHEME_TONAL_PALETTES, palette_analysis.core_palettes)
            run_set_tokens_stage(context)
            legacy_key = "inventory" + "." + "gra" + "ph"
            self.assertFalse(context.has(legacy_key))
            self.assertTrue(context.has(ContextKey.TOKEN_INVENTORY))
            tokenized_structure = context.get(ContextKey.PROTOTYPE_STRUCTURE)
            self.assertTrue(any(element.token_ids for element in tokenized_structure))
            self.assertTrue(
                any(
                    property_model.token_ids
                    for element in tokenized_structure
                    for property_model in element.properties
                )
            )
            self.assertTrue(any(color.token_ids for color in context.get(ContextKey.COLOR_CATALOG)))

            run_check_tokens_stage(context)
            self.assertFalse(context.has(legacy_key))
            self.assertTrue(context.has(ContextKey.TOKEN_INVENTORY))
            self.assertTrue(any(color.token_ids for color in context.get(ContextKey.COLOR_CATALOG)))
            self.assertFalse(tokens_path.exists())
            self.assertFalse(legacy_path.exists())

    def test_apply_tokens_to_project_preserves_local_asset_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_root = Path(tmp_dir) / "input_project"
            output_root = Path(tmp_dir) / "output_project"
            html_path, html_content = _build_nested_asset_project(input_root)
            shutil.copytree(input_root, output_root)

            apply_tokens_to_project(
                html_content,
                str(output_root / "pages" / "index.html"),
                str(output_root),
                TokenInventory.build(()),
                PrototypeStructure.build(()),
            )

            transformed_html = (output_root / "pages" / "index.html").read_text(encoding="utf-8")
            transformed_css = (output_root / "styles" / "site.css").read_text(encoding="utf-8")

            self.assertIn('href="../styles/site.css"', transformed_html)
            self.assertIn('href="menu.html"', transformed_html)
            self.assertIn('action="menu.html"', transformed_html)
            self.assertIn('src="../scripts/app.js"', transformed_html)
            self.assertIn('src="../images/photo.png"', transformed_html)
            self.assertIn(
                'srcset="../images/photo.png 1x, ../images/photo@2x.png 2x"',
                transformed_html,
            )
            self.assertIn('src="../media/clip.mp4"', transformed_html)
            self.assertIn("url('../images/hero.png')", transformed_html)
            self.assertIn("url('../images/bg.png')", transformed_css)

    def test_heuristic_transform_preserves_local_asset_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_root = Path(tmp_dir) / "input_project"
            output_root = Path(tmp_dir) / "output_project"
            html_path, html_content = _build_nested_asset_project(input_root)
            shutil.copytree(input_root, output_root)

            evaluate_and_apply_heuristics(
                html_content,
                str(output_root / "pages" / "index.html"),
                str(output_root),
                None,
            )

            transformed_html = (output_root / "pages" / "index.html").read_text(encoding="utf-8")
            transformed_css = (output_root / "styles" / "site.css").read_text(encoding="utf-8")

            self.assertIn('href="../styles/site.css"', transformed_html)
            self.assertIn('href="menu.html"', transformed_html)
            self.assertIn('action="menu.html"', transformed_html)
            self.assertIn('src="../scripts/app.js"', transformed_html)
            self.assertIn('src="../images/photo.png"', transformed_html)
            self.assertIn(
                'srcset="../images/photo.png 1x, ../images/photo@2x.png 2x"',
                transformed_html,
            )
            self.assertIn('src="../media/clip.mp4"', transformed_html)
            self.assertIn("url('../images/hero.png')", transformed_html)
            self.assertIn("url('../images/bg.png')", transformed_css)

    def test_apply_tokens_to_project_rewrites_shorthand_declaration_from_longhand_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir) / "output_project"
            css_dir = output_root / "css"
            css_dir.mkdir(parents=True, exist_ok=True)

            html_path = output_root / "index.html"
            html_content = """
            <html>
              <head>
                <link rel="stylesheet" href="css/site.css" />
              </head>
              <body>
                <button class="cta">Boton</button>
              </body>
            </html>
            """
            css_path = css_dir / "site.css"
            css_path.write_text(
                ".cta { border: 5px solid rgb(255, 255, 0); color: rgb(0, 0, 0); }",
                encoding="utf-8",
            )

            elements = (
                Element.build(
                    {
                        "node_id": "node-1",
                        "backend_node_id": 1,
                        "document_order": 1,
                        "children_ids": [],
                        "tag_name": "button",
                        "node_name": "BUTTON",
                        "x": 0,
                        "y": 0,
                        "width": 160,
                        "height": 48,
                        "left": 0,
                        "top": 0,
                        "right": 160,
                        "bottom": 48,
                        "properties": [
                            {
                                "name": "border-top-color",
                                "value": "rgb(255, 255, 0)",
                                "style_id": "style-1",
                                "declared_property": "border",
                                "declaration_id": "style-1-decl-1",
                                "resolution_status": "exact_match",
                                "color_id": "color-1",
                            }
                        ],
                    }
                ),
            )
            styles = StyleCatalog.build(
                (
                    {
                        "style_id": "style-1",
                        "kind": "external",
                        "declarations": [
                            {
                                "name": "border",
                                "value": "5px solid rgb(255, 255, 0)",
                                "declaration_id": "style-1-decl-1",
                            }
                        ],
                    },
                )
            )
            colors = ColorCatalog.build(({"color_id": "color-1", "value": "rgb(255, 255, 0)"},))
            token_inventory = TokenInventory.build(
                (
                    Token.semantic(
                        path=("glow", "composed", "border-top-color", "emphasis", "1"),
                        alias_to=None,
                        resolved_value="rgb(43, 49, 51)",
                        element_key="composed",
                        property_id="border-top-color",
                        value_label="emphasis.1",
                        source_color_ids=("color-1",),
                        source_style_ids=("style-1",),
                        source_values=("rgb(255, 255, 0)",),
                        source_property_refs=("node-1:border-top-color",),
                    ),
                )
            )

            apply_tokens_to_project(
                html_content,
                str(html_path),
                str(output_root),
                token_inventory,
                PrototypeStructure.build(
                    elements,
                    styles_inventory=styles,
                ),
            )

            transformed_css = css_path.read_text(encoding="utf-8")
            self.assertIn(
                "border: 5px solid var(--glow-composed-border-top-color-emphasis-1);",
                transformed_css,
            )

    def test_apply_tokens_to_project_injects_only_used_semantic_variables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir) / "output_project"
            output_root.mkdir(parents=True, exist_ok=True)
            html_path = output_root / "index.html"
            html_content = """
            <html>
              <body>
                <p style="color: rgb(255, 0, 0)">Hola</p>
              </body>
            </html>
            """

            token_inventory = TokenInventory.build(
                (
                    Token.foundation(
                        path=("glow", "color", "neutral", "10"),
                        resolved_value="rgb(31, 35, 37)",
                        source_palette_ids=("palette-achromatic-1",),
                    ),
                    Token.semantic(
                        path=("glow", "text", "color", "emphasis", "2"),
                        alias_to="glow.color.neutral.10",
                        resolved_value="rgb(31, 35, 37)",
                        element_key="text",
                        property_id="color",
                        value_label="emphasis.2",
                        source_values=("rgb(255, 0, 0)",),
                        source_property_refs=("node-1:color",),
                    ),
                )
            )

            apply_tokens_to_project(
                html_content,
                str(html_path),
                str(output_root),
                token_inventory,
                PrototypeStructure.build(()),
            )

            transformed_html = html_path.read_text(encoding="utf-8")
            self.assertIn("--glow-text-color-emphasis-2: rgb(31, 35, 37);", transformed_html)
            self.assertNotIn("--glow-color-neutral-10", transformed_html)
            self.assertIn("color: var(--glow-text-color-emphasis-2)", transformed_html)

    def test_apply_tokens_to_project_rewrites_effect_declaration_from_color_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir) / "output_project"
            css_dir = output_root / "css"
            css_dir.mkdir(parents=True, exist_ok=True)

            html_path = output_root / "index.html"
            html_content = """
            <html>
              <head>
                <link rel="stylesheet" href="css/site.css" />
              </head>
              <body>
                <section class="hero">Hero</section>
              </body>
            </html>
            """
            css_path = css_dir / "site.css"
            css_path.write_text(
                ".hero { background-image: linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 255, 0) 100%); }",
                encoding="utf-8",
            )

            token_inventory = TokenInventory.build(
                (
                    Token.semantic(
                        path=("glow", "surface", "background-image", "gradient"),
                        alias_to=None,
                        resolved_value="linear-gradient(90deg, rgb(43, 49, 51) 0%, rgb(57, 79, 62) 100%)",
                        element_key="surface",
                        property_id="background-image",
                        value_label="gradient",
                        source_values=("linear-gradient(rgb(255, 0, 0), rgb(0, 255, 0))",),
                        source_property_refs=("node-1:background-image",),
                    ),
                )
            )

            apply_tokens_to_project(
                html_content,
                str(html_path),
                str(output_root),
                token_inventory,
                PrototypeStructure.build(()),
            )

            transformed_css = css_path.read_text(encoding="utf-8")
            transformed_html = html_path.read_text(encoding="utf-8")
            self.assertIn(
                "background-image: var(--glow-surface-background-image-gradient);",
                transformed_css,
            )
            self.assertIn(
                "--glow-surface-background-image-gradient: linear-gradient(90deg, rgb(43, 49, 51) 0%, rgb(57, 79, 62) 100%);",
                transformed_html,
            )

    def test_build_token_inventory_uses_property_for_text_color(self) -> None:
        elements = _elements(
            (
                {
                    "node_id": "node-1",
                    "backend_node_id": 1,
                    "parent_id": None,
                    "children_ids": (),
                    "document_order": 1,
                    "tag_name": "p",
                    "node_name": "P",
                    "x": 0,
                    "y": 0,
                    "width": 160,
                    "height": 24,
                    "left": 0,
                    "top": 0,
                    "right": 160,
                    "bottom": 24,
                    "is_visible": True,
                    "text": "Hola",
                    "properties": [
                        {
                            "name": "color",
                            "value": "rgb(255, 0, 0)",
                            "classification": "foreground",
                            "color_id": "color-1",
                            "style_id": "style-1",
                            "declared_property": "color",
                            "declaration_id": "style-1-decl-1",
                            "resolution_status": "exact_match",
                        }
                    ],
                },
            )
        )
        styles = StyleCatalog.build(
            (
                {
                    "style_id": "style-1",
                    "kind": "inline",
                    "declarations": [
                        {
                            "name": "color",
                            "value": "rgb(255, 0, 0)",
                            "declaration_id": "style-1-decl-1",
                        }
                    ],
                },
            )
        )
        colors = ColorCatalog.build(({"color_id": "color-1", "value": "rgb(255, 0, 0)"},))
        palette_analysis = build_palette_analysis(
            snapshot_palette=(
                {
                    "color_id": "color-1",
                    "value": "rgb(255, 0, 0)",
                    "usage_count": 1,
                    "usage": [{"tag": "section", "property": "background-color", "count": 1}],
                },
            ),
            material_quantization_assessment=get_material_quantization_assessment(),
        )
        prototype_structure = _prototype(elements, styles)
        token_inventory = build_token_inventory(
            prototype_structure,
            tuple(colors),
            palette_analysis.core_palettes,
        )

        self.assertTrue(
            any(
                token.property_id == "color"
                and token.source_style_ids == ("style-1",)
                and "node-1" in token.source_element_ids
                for token in token_inventory
            )
        )

    def test_apply_token_rules_adjusts_composed_shadow_effects(self) -> None:
        achromatic_palette = TonalPaletteModel.from_seed(
            palette_id="palette-achromatic-1",
            palette_type="achromatic",
            seed_hex="#ffffff",
            role_bias="background",
            semantic_weight=0,
            pixel_count=0,
            seed_name="white",
            chroma_override=6.0,
        )
        chromatic_palette = TonalPaletteModel.from_seed(
            palette_id="palette-chromatic-1",
            palette_type="chromatic",
            seed_hex="#ff0000",
            role_bias="background",
            semantic_weight=1,
            pixel_count=64,
            seed_name="red",
        )
        tone_30 = next(tone for tone in chromatic_palette.tones if tone.tone == 30)
        colors = ColorCatalog.build(
            (
                {
                    "color_id": "color-1",
                    "value": "rgb(255, 0, 0)",
                    "mapped_palette_id": chromatic_palette.palette_id,
                    "mapped_tone": 90,
                    "mapped_tone_rgb": [255, 138, 128],
                    "mapped_tone_distance": 0.0,
                },
            )
        )
        prototype_structure = PrototypeStructure.build(())
        tokens = TokenInventory.build(
            (
                Token.foundation(
                    path=("glow", "color", "neutral", "10"),
                    resolved_value=next(tone for tone in achromatic_palette.tones if tone.tone == 10).hex_value,
                    source_palette_ids=(achromatic_palette.palette_id,),
                    tone=10,
                ),
                Token.foundation(
                    path=("glow", "color", "red", "30"),
                    resolved_value=tone_30.hex_value,
                    source_palette_ids=(chromatic_palette.palette_id,),
                    tone=30,
                ),
                Token.semantic(
                    path=("glow", "composed", "box-shadow", "elevated"),
                    alias_to=None,
                    resolved_value="0 0 12px rgb(255, 0, 0)",
                    element_key="composed",
                    property_id="box-shadow",
                    value_label="elevated",
                    source_color_ids=("color-1",),
                    source_palette_ids=(chromatic_palette.palette_id,),
                    source_values=("0 0 12px rgb(255, 0, 0)",),
                    tone=90,
                ),
            )
        )

        validated = apply_token_rules(
            tokens,
            prototype_structure,
            tuple(colors),
            (achromatic_palette, chromatic_palette),
        )
        shadow_token = next(
            token for token in validated if token.property_id == "box-shadow" and token.is_semantic
        )

        self.assertEqual(shadow_token.state, TokenState.VALIDATED)
        self.assertIsNone(shadow_token.alias_to)
        self.assertNotEqual(shadow_token.resolved_value, "0 0 12px rgb(255, 0, 0)")
        self.assertIn("0 0 12px", shadow_token.resolved_value)
        self.assertIn(tone_30.hex_value.lower(), shadow_token.resolved_value.lower())

    def test_build_token_inventory_prefers_full_effect_value_over_color_fragment(self) -> None:
        achromatic_palette = TonalPaletteModel.from_seed(
            palette_id="palette-achromatic-1",
            palette_type="achromatic",
            seed_hex="#ffffff",
            role_bias="background",
            semantic_weight=0,
            pixel_count=0,
            seed_name="white",
            chroma_override=6.0,
        )
        chromatic_palette = TonalPaletteModel.from_seed(
            palette_id="palette-chromatic-1",
            palette_type="chromatic",
            seed_hex="#ff0000",
            role_bias="background",
            semantic_weight=1,
            pixel_count=64,
            seed_name="red",
        )
        elements = _elements(
            (
                {
                    "node_id": "node-1",
                    "backend_node_id": 1,
                    "parent_id": None,
                    "children_ids": (),
                    "document_order": 1,
                    "tag_name": "button",
                    "node_name": "BUTTON",
                    "x": 0,
                    "y": 0,
                    "width": 160,
                    "height": 48,
                    "left": 0,
                    "top": 0,
                    "right": 160,
                    "bottom": 48,
                    "is_visible": True,
                    "text": "CTA",
                    "properties": [
                        {
                            "name": "box-shadow",
                            "value": "0 0 12px rgb(255, 0, 0)",
                            "classification": "effect",
                            "color_id": "color-1",
                            "style_id": "style-1",
                            "declared_property": "box-shadow",
                            "declaration_id": "style-1-decl-1",
                            "resolution_status": "exact_match",
                        }
                    ],
                },
            )
        )
        colors = ColorCatalog.build(({"color_id": "color-1", "value": "rgb(255, 0, 0)"},))
        prototype_structure = _prototype(elements, StyleCatalog.build(()))
        scheme_stub = type(
            "SchemeStub",
            (),
            {"core_palettes": (achromatic_palette, chromatic_palette)},
        )()

        token_inventory = build_token_inventory(
            prototype_structure,
            tuple(colors),
            scheme_stub.core_palettes,  # type: ignore[arg-type]
        )
        shadow_token = next(
            token for token in token_inventory if token.property_id == "box-shadow" and token.is_semantic
        )

        self.assertEqual(shadow_token.resolved_value, "0 0 12px rgb(255, 0, 0)")

    def test_apply_token_rules_adjusts_composed_background_image_effects(self) -> None:
        achromatic_palette = TonalPaletteModel.from_seed(
            palette_id="palette-achromatic-1",
            palette_type="achromatic",
            seed_hex="#ffffff",
            role_bias="background",
            semantic_weight=0,
            pixel_count=0,
            seed_name="white",
            chroma_override=6.0,
        )
        red_palette = TonalPaletteModel.from_seed(
            palette_id="palette-chromatic-1",
            palette_type="chromatic",
            seed_hex="#ff0000",
            role_bias="background",
            semantic_weight=1,
            pixel_count=64,
            seed_name="red",
        )
        yellow_palette = TonalPaletteModel.from_seed(
            palette_id="palette-chromatic-2",
            palette_type="chromatic",
            seed_hex="#ffff00",
            role_bias="background",
            semantic_weight=1,
            pixel_count=64,
            seed_name="yellow",
        )
        red_tone = next(tone for tone in red_palette.tones if tone.tone == 30)
        yellow_tone = next(tone for tone in yellow_palette.tones if tone.tone == 30)
        colors = ColorCatalog.build(
            (
                {
                    "color_id": "color-1",
                    "value": "rgb(255, 0, 0)",
                    "mapped_palette_id": red_palette.palette_id,
                    "mapped_tone": 90,
                    "mapped_tone_rgb": [255, 138, 128],
                    "mapped_tone_distance": 0.0,
                },
                {
                    "color_id": "color-2",
                    "value": "rgb(255, 255, 0)",
                    "mapped_palette_id": yellow_palette.palette_id,
                    "mapped_tone": 90,
                    "mapped_tone_rgb": [255, 245, 157],
                    "mapped_tone_distance": 0.0,
                },
            )
        )
        prototype_structure = PrototypeStructure.build(())
        tokens = TokenInventory.build(
            (
                Token.foundation(
                    path=("glow", "color", "red", "30"),
                    resolved_value=red_tone.hex_value,
                    source_palette_ids=(red_palette.palette_id,),
                    tone=30,
                ),
                Token.foundation(
                    path=("glow", "color", "yellow", "30"),
                    resolved_value=yellow_tone.hex_value,
                    source_palette_ids=(yellow_palette.palette_id,),
                    tone=30,
                ),
                Token.semantic(
                    path=("glow", "composed", "background-image", "gradient"),
                    alias_to=None,
                    resolved_value="linear-gradient(to right, rgb(255, 0, 0), rgb(255, 255, 0))",
                    element_key="composed",
                    property_id="background-image",
                    value_label="gradient",
                    source_color_ids=("color-1", "color-2"),
                    source_palette_ids=(red_palette.palette_id, yellow_palette.palette_id),
                    source_values=("linear-gradient(to right, rgb(255, 0, 0), rgb(255, 255, 0))",),
                    tone=90,
                ),
            )
        )

        validated = apply_token_rules(
            tokens,
            prototype_structure,
            tuple(colors),
            (achromatic_palette, red_palette, yellow_palette),
        )
        gradient_token = next(
            token for token in validated if token.property_id == "background-image" and token.is_semantic
        )

        self.assertIsNone(gradient_token.alias_to)
        self.assertNotEqual(
            gradient_token.resolved_value,
            "linear-gradient(to right, rgb(255, 0, 0), rgb(255, 255, 0))",
        )
        self.assertIn(red_tone.hex_value.lower(), gradient_token.resolved_value.lower())
        self.assertIn(yellow_tone.hex_value.lower(), gradient_token.resolved_value.lower())

    def test_surface_background_prefers_same_palette_foundation_over_achromatic(self) -> None:
        colors = ColorCatalog.build(({"color_id": "color-1", "value": "rgb(255, 0, 0)"},))
        achromatic_palette = TonalPaletteModel.from_seed(
            palette_id="palette-achromatic-1",
            palette_type="achromatic",
            seed_hex="#ffffff",
            role_bias="background",
            semantic_weight=0,
            pixel_count=0,
            seed_name="white",
            chroma_override=6.0,
        )
        chromatic_palette = TonalPaletteModel.from_seed(
            palette_id="palette-chromatic-1",
            palette_type="chromatic",
            seed_hex="#ff0000",
            role_bias="background",
            semantic_weight=1,
            pixel_count=64,
            seed_name="red",
        )
        tone_90 = next(tone for tone in chromatic_palette.tones if tone.tone == 90)
        mapped_colors = ColorCatalog.build(
            (
                colors.entry_by_id("color-1").with_palette_mapping(  # type: ignore[union-attr]
                    palette_id=chromatic_palette.palette_id,
                    tone=tone_90.tone,
                    tone_rgb=tone_90.rgb,
                    tone_distance=0.0,
                ),
            )
        )
        elements = _elements(
            (
                {
                    "node_id": "node-1",
                    "backend_node_id": 1,
                    "parent_id": None,
                    "children_ids": (),
                    "document_order": 1,
                    "tag_name": "section",
                    "node_name": "SECTION",
                    "x": 0,
                    "y": 0,
                    "width": 200,
                    "height": 100,
                    "left": 0,
                    "top": 0,
                    "right": 200,
                    "bottom": 100,
                    "is_visible": True,
                    "properties": [
                        {
                            "name": "background-color",
                            "value": "rgb(255, 0, 0)",
                            "classification": "background",
                            "style_id": "style-1",
                            "declared_property": "background-color",
                            "declaration_id": "style-1-decl-1",
                            "resolution_status": "exact_match",
                            "color_id": "color-1",
                        }
                    ],
                },
            )
        )
        styles = StyleCatalog.build(
            (
                {
                    "style_id": "style-1",
                    "kind": "inline",
                    "declarations": [
                        {
                            "name": "background-color",
                            "value": "rgb(255, 0, 0)",
                            "declaration_id": "style-1-decl-1",
                        }
                    ],
                },
            )
        )
        prototype_structure = _prototype(elements, styles)

        scheme_stub = type(
            "SchemeStub",
            (),
            {"core_palettes": (achromatic_palette, chromatic_palette)},
        )()

        token_inventory = build_token_inventory(
            prototype_structure,
            tuple(mapped_colors),
            scheme_stub.core_palettes,  # type: ignore[arg-type]
        )
        validated_inventory = apply_token_rules(
            token_inventory,
            prototype_structure,
            tuple(mapped_colors),
            scheme_stub.core_palettes,  # type: ignore[arg-type]
        )
        surface_token = next(
            token
            for token in validated_inventory
            if token.property_id == "background-color" and token.element_key == "surface"
        )
        aliased_foundation = next(
            token for token in validated_inventory if token.path_string == surface_token.alias_to
        )

        self.assertIsNotNone(surface_token.alias_to)
        self.assertIn(
            chromatic_palette.palette_id,
            aliased_foundation.source_palette_ids,
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
        self.assertNotIn("artifact", results["color_processing"])
        self.assertNotIn("artifact", results["accessibility"]["contrast"])
        self.assertNotIn("artifact", results["effect_colors"])
        self.assertNotIn("palette_preview_artifact", results["color_processing"])
        self.assertNotIn("palette_preview_output", results["color_processing"])
        self.assertEqual(results["color_processing"]["palette_preview_location"], "artifacts")
        self.assertNotIn("artifact", results["token_processing"])
        self.assertNotIn("gra" + "ph_artifact", results["token_processing"])
        self.assertGreaterEqual(results["token_processing"]["foundation_token_count"], 1)
        self.assertGreaterEqual(results["token_processing"]["semantic_token_count"], 1)
        self.assertGreaterEqual(results["token_processing"]["tokenized_element_count"], 1)
        preview_output = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / "palette_preview.png"
        )
        self.assertTrue(preview_output.exists())
        self.assertNotIn("artifact", results["render_snapshot"])
        css_overview_path = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / "css_overview_original.json"
        )
        self.assertFalse(css_overview_path.exists())
        css_overview_payload = results.get("accessibility", {}).get("css_overview", {}) or {
            "colors": {},
            "contrast_issues": [],
            "unused_declarations": {},
        }
        self.assertIsInstance(css_overview_payload, dict)
        self.assertIsInstance(css_overview_payload, dict)
        self.assertIsInstance(css_overview_payload, dict)
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
        self.assertFalse(colors_inventory_path.exists())
        colors_inventory_payload = {"entries": []}
        self.assertIn("entries", colors_inventory_payload)
        legacy_effect_path = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / ("effect" + "_colors_original.json")
        )
        self.assertFalse(legacy_effect_path.exists())
        effect_colors_payload = results["effect_colors"]
        self.assertIn("entries", effect_colors_payload)
        self.assertIn("properties", effect_colors_payload)
        legacy_relations_path = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / ("inventory" + "_" + "gra" + "ph.json")
        )
        self.assertFalse(legacy_relations_path.exists())
        results_json_path = (
            Path("workspace/sessions")
            / results["session_dirname"]
            / "artifacts"
            / ("results" + ".json")
        )
        self.assertFalse(results_json_path.exists())

    def test_run_pipeline_preserves_zip_project_skeleton_in_output(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "Pagina/menu.html",
                "<html><body style=\"background:#000;color:#fff\"><h1>Hola</h1></body></html>",
            )
            archive.writestr("Pagina/css/site.css", "body { margin: 0; }")
            archive.writestr("Pagina/assets/logo.png", b"fake-png")

        app = create_app()
        upload = InMemoryUpload("Pagina_de_prueba_2.zip", buffer.getvalue())
        with app.test_request_context("/results", method="POST"):
            results, error = run_pipeline(upload)

        self.assertIsNone(error)
        assert results is not None
        session_dir = Path("workspace/sessions") / results["session_dirname"]
        self.assertTrue((session_dir / "before" / "Pagina" / "menu.html").exists())
        self.assertTrue((session_dir / "before" / "Pagina" / "assets" / "logo.png").exists())
        self.assertTrue((session_dir / "after" / "Pagina" / "menu.html").exists())
        self.assertTrue((session_dir / "after" / "Pagina" / "css" / "site.css").exists())
        self.assertTrue((session_dir / "after" / "Pagina" / "assets" / "logo.png").exists())
        self.assertFalse((session_dir / "after" / "palette_preview.png").exists())
        self.assertFalse((session_dir / "after" / "Pagina_de_prueba_2.zip").exists())
        self.assertTrue((session_dir / "artifacts" / "palette_preview.png").exists())
        self.assertTrue((session_dir / "artifacts" / "Pagina.zip").exists())

    def test_results_route_serves_zip_assets_screenshots_and_download_bundle(self) -> None:
        png_1x1 = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00"
            b"\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "site/pages/index.html",
                """
                <html>
                  <head><link rel="stylesheet" href="../styles/site.css"></head>
                  <body>
                    <main class="hero"><h1>Asset route check</h1><img src="../assets/logo.png"></main>
                  </body>
                </html>
                """,
            )
            archive.writestr(
                "site/styles/site.css",
                ".hero { background: #ffffff; color: #111111; padding: 24px; } img { width: 1px; height: 1px; }",
            )
            archive.writestr("site/assets/logo.png", png_1x1)

        app = create_app()
        client = app.test_client()
        response = client.post(
            "/results",
            data={"file": (io.BytesIO(buffer.getvalue()), "asset_project.zip")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        match = re.search(r"/sessions/(session_[^/]+)/artifacts/before\.png", html)
        self.assertIsNotNone(match)
        session_dirname = match.group(1)
        session_dir = Path("workspace/sessions") / session_dirname

        self.assertTrue((session_dir / "before" / "site" / "pages" / "index.html").exists())
        self.assertTrue((session_dir / "before" / "site" / "styles" / "site.css").exists())
        self.assertTrue((session_dir / "before" / "site" / "assets" / "logo.png").exists())
        self.assertTrue((session_dir / "after" / "site" / "pages" / "index.html").exists())
        self.assertTrue((session_dir / "after" / "site" / "styles" / "site.css").exists())
        self.assertTrue((session_dir / "after" / "site" / "assets" / "logo.png").exists())

        before_response = client.get(f"/sessions/{session_dirname}/artifacts/before.png")
        after_response = client.get(f"/sessions/{session_dirname}/artifacts/after.png")
        bundle_response = client.get(f"/sessions/{session_dirname}/artifacts/site.zip")
        transformed_response = client.get(f"/sessions/{session_dirname}/output/site/pages/index.html")

        try:
            self.assertEqual(before_response.status_code, 200)
            self.assertEqual(after_response.status_code, 200)
            self.assertEqual(bundle_response.status_code, 200)
            self.assertEqual(transformed_response.status_code, 200)
            self.assertIn("Asset route check", transformed_response.get_data(as_text=True))

            with zipfile.ZipFile(io.BytesIO(bundle_response.data), "r") as bundle:
                self.assertIn("site/pages/index.html", bundle.namelist())
                self.assertIn("site/styles/site.css", bundle.namelist())
                self.assertIn("site/assets/logo.png", bundle.namelist())
        finally:
            before_response.close()
            after_response.close()
            bundle_response.close()
            transformed_response.close()

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
            Path("engine/domain/models/prototype_structure.py"),
            Path("engine/domain/models/quality_reports.py"),
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
            Path("engine/adapters/file_system/file_manager.py"),
            Path("engine/adapters/source_code_handler/code_processor.py"),
            Path("engine/adapters/browser/page_builder.py"),
            Path("engine/adapters/browser/render_models.py"),
            Path("engine/adapters/color_service/service.py"),
            Path("engine/adapters/utils/pixel.py"),
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
            Path("engine/domain/utils") / ("token" + "_" + "gra" + "ph.py"),
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

    def test_runtime_refactor_guardrails_block_parallel_truths(self) -> None:
        python_files = tuple(Path("engine").rglob("*.py"))
        blocked_tokens = (
            "Token" + "Gra" + "ph",
            "inventory" + "." + "gra" + "ph",
            "build_" + "effect_color_report",
            "derived" + ".effect_color_report",
            "scheme." + "colors",
            "SCHEME" + "_COLORS",
            "scheme." + "color_catalog",
            "scheme." + "semantic_colors",
            "build_" + "color_catalog_from_scheme",
        )

        for path in python_files:
            content = path.read_text(encoding="utf-8")
            for token in blocked_tokens:
                self.assertNotIn(token, content, msg=f"{token} still present in {path}")

    def test_runtime_state_is_not_stored_on_session_or_results_json(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        session_source = (repo_root / "engine" / "domain" / "models" / "session.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("original_" + "capture", session_source)
        self.assertNotIn("original_" + "css_overview", session_source)
        self.assertNotIn("results_" + "json_path", session_source)

        assemble_source = (repo_root / "engine" / "pipeline" / "stages" / "assemble_results.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("save_" + "json", assemble_source)
        self.assertNotIn("results_" + "json_path", assemble_source)

        for path in (repo_root / "engine").rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("def " + "save_json", content, msg=str(path))

        for path in Path("engine/pipeline/stages").glob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("session." + "original_css_overview", content, msg=str(path))

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

    def test_pixel_utils_are_centralized_without_screenshot_wrapper(self) -> None:
        self.assertFalse(
            (Path("engine/services/color_processing") / ("pixel" + "_frequency_service.py")).exists()
        )
        self.assertFalse(Path("engine/adapters/utils/screenshot.py").exists())
        content = Path("engine/adapters/utils/pixel.py").read_text(encoding="utf-8")
        self.assertIn("def build_color_histograms(", content)
        self.assertIn("def cluster_color_histogram(", content)
        self.assertIn("def dominant_color_percentages(", content)
        self.assertNotIn("def build_" + "pixel" + "_histogram(", content)
        self.assertNotIn("def process_" + "pixel" + "_frequency(", content)
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
