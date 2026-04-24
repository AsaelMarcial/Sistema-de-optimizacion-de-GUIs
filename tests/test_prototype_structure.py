from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.adapters.browser.render_models import RenderArtifacts, RenderSnapshot
from engine.domain.models.color import Color, ColorCatalog
from engine.domain.models.element import Element, Property
from engine.domain.models.palette import CorePalettesModel, TonalPaletteModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import Session
from engine.domain.models.style import StyleCatalog
from engine.domain.utils.color_usage import build_color_usage_catalog
from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.assemble_results import _effect_colors_payload
from engine.pipeline.stages.build_color_scheme import run_stage as run_build_color_scheme_stage
from engine.pipeline.stages.build_contrast_report import run_stage as run_build_contrast_report_stage
from engine.pipeline.stages.capture_original_state import run_stage as run_capture_original_state_stage


def _build_session(
    base_dir: Path,
    *,
    input_html_content: str = "<html></html>",
) -> Session:
    return Session.build(
        session_id="prototype-test",
        base_dir=str(base_dir),
        upload_path="fixture.html",
        html_relative_path="index.html",
        input_html_content=input_html_content,
    ).ensure_exists()


def _sample_elements() -> tuple[Element, ...]:
    return (
        Element.build(
            {
                "node_id": "body-node",
                "backend_node_id": 1,
                "document_order": 1,
                "children_ids": ["title-node"],
                "tag_name": "body",
                "node_name": "BODY",
                "xpath": "/html[1]/body[1]",
                "is_visible": True,
                "is_leaf": False,
                "properties": [
                    {
                        "name": "background-color",
                        "value": "rgb(255, 255, 255)",
                        "classification": "background",
                        "color_id": "color-1",
                        "style_id": "style-1",
                        "declaration_id": "decl-1",
                        "declared_property": "background-color",
                        "resolution_status": "exact_match",
                    }
                ],
            }
        ),
        Element.build(
            {
                "node_id": "title-node",
                "backend_node_id": 2,
                "document_order": 2,
                "parent_id": "body-node",
                "children_ids": [],
                "tag_name": "h1",
                "node_name": "H1",
                "html_id": "title",
                "xpath": "/html[1]/body[1]/h1[1]",
                "is_visible": True,
                "is_leaf": True,
                "text": "Title",
                "effective_background": "rgb(255, 255, 255)",
                "properties": [
                    {
                        "name": "color",
                        "value": "rgb(20, 20, 20)",
                        "classification": "foreground",
                        "color_id": "color-2",
                        "style_id": "style-2",
                        "declaration_id": "decl-2",
                        "declared_property": "color",
                        "resolution_status": "exact_match",
                    },
                    {
                        "name": "box-shadow",
                        "value": "rgba(0, 0, 0, 0.2) 0px 1px 2px",
                        "classification": "effect",
                        "color_id": "color-3",
                        "style_id": "style-2",
                        "declaration_id": "decl-3",
                        "declared_property": "box-shadow",
                        "resolution_status": "exact_match",
                    },
                ],
            }
        ),
    )


def _sample_colors() -> ColorCatalog:
    return ColorCatalog.build(
        (
            {
                "color_id": "color-1",
                "value": "rgb(255, 255, 255)",
                "usage_count": 1,
                "node_ids": ["body-node"],
                "usage": [{"tag": "body", "property": "background-color", "count": 1}],
            },
            {
                "color_id": "color-2",
                "value": "rgb(20, 20, 20)",
                "usage_count": 1,
                "node_ids": ["title-node"],
                "usage": [{"tag": "h1", "property": "color", "count": 1}],
            },
            {
                "color_id": "color-3",
                "value": "rgba(0, 0, 0, 0.2)",
                "usage_count": 1,
                "node_ids": ["title-node"],
                "usage": [{"tag": "h1", "property": "box-shadow", "count": 1}],
            },
        )
    )


def _sample_contrast_css_overview() -> dict[str, object]:
    return {
        "contrast_issues": [
            {
                "node_id": "title-node",
                "selector": "#title",
                "tag_name": "h1",
                "text_sample": "Title",
                "contrast_ratio": 3.4,
                "required_ratio": 4.5,
                "is_large_text": False,
                "font_size_px": 16.0,
                "font_weight": 400,
                "bounds": {"x": 12, "y": 24, "width": 160, "height": 32},
                "foreground": {
                    "css": "rgb(20, 20, 20)",
                    "hex": "#141414",
                    "alpha": 1.0,
                },
                "background": {
                    "css": "rgb(255, 255, 255)",
                    "hex": "#ffffff",
                    "alpha": 1.0,
                },
            }
        ]
    }


class PrototypeStructureTests(unittest.TestCase):
    def test_pipeline_context_accepts_prototype_structure_root(self) -> None:
        context = PipelineContext(file=None)
        prototype_structure = PrototypeStructure.build(_sample_elements())
        context.set("prototype_structure", prototype_structure)
        self.assertIs(context.get("prototype_structure"), prototype_structure)

    def test_capture_original_state_populates_canonical_nodes(self) -> None:
        artifacts = RenderArtifacts(
            screenshot_path=None,
            snapshot=RenderSnapshot(
                metadata={"nodeCount": 2},
                document={},
                nodes=_sample_elements(),
            ),
            styles_inventory_seed=StyleCatalog(),
            colors_inventory_seed=_sample_colors(),
        )
        class FakePageBuilder:
            def __init__(self, artifacts: RenderArtifacts) -> None:
                self.artifacts = artifacts
                self.calls: list[dict[str, str | None]] = []

            def capture_state_artifacts(
                self,
                *,
                artifacts_dir: str | None = None,
                screenshot_filename: str | None = None,
            ) -> RenderArtifacts:
                self.calls.append(
                    {
                        "artifacts_dir": artifacts_dir,
                        "screenshot_filename": screenshot_filename,
                    }
                )
                return self.artifacts

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            page_builder = FakePageBuilder(artifacts)
            context = PipelineContext(file=None)
            context.set("session", _build_session(tmp_path))
            context.set("session.page_builder", page_builder)
            run_capture_original_state_stage(context)

        prototype_structure = context.get("prototype_structure")
        self.assertIsInstance(prototype_structure, PrototypeStructure)
        self.assertTrue(context.has("color.catalog"))
        self.assertTrue(context.has("derived.raw_css_overview"))
        self.assertTrue(context.has("derived.raw_snapshot_metadata"))
        self.assertFalse(context.has("session.before_capture"))
        self.assertEqual(page_builder.calls[0]["screenshot_filename"], Session.ORIGINAL_SCREENSHOT_NAME)
        self.assertEqual(len(prototype_structure), 2)
        self.assertEqual(prototype_structure.indexes.by_tag["body"], ("body-node",))
        self.assertEqual(prototype_structure.indexes.by_depth[0], ("body-node",))
        self.assertEqual(prototype_structure.indexes.by_depth[1], ("title-node",))
        self.assertIn("foreground", prototype_structure.indexes.by_classification)
        self.assertIn("effect", prototype_structure.indexes.by_classification)

        title_properties = {
            property_model.name: property_model
            for property_model in prototype_structure.properties_for("title-node")
        }
        self.assertEqual(title_properties["color"].classification, "foreground")
        self.assertEqual(title_properties["box-shadow"].classification, "effect")
        self.assertEqual(title_properties["color"].color_id, "color-2")

    def test_prototype_structure_navigation_and_effective_color_helpers(self) -> None:
        prototype_structure = PrototypeStructure.build(_sample_elements())
        colors_inventory = _sample_colors()

        parent = prototype_structure.parent_of("title-node")
        self.assertIsNotNone(parent)
        self.assertEqual(parent.node_id, "body-node")
        self.assertEqual(
            tuple(node.node_id for node in prototype_structure.ancestors_of("title-node")),
            ("body-node",),
        )
        self.assertEqual(
            tuple(node.node_id for node in prototype_structure.children_of("body-node")),
            ("title-node",),
        )
        self.assertEqual(
            tuple(node.node_id for node in prototype_structure.descendants_of("body-node")),
            ("title-node",),
        )
        self.assertEqual(
            prototype_structure.surface_container_of("title-node").node_id,
            "body-node",
        )
        self.assertEqual(
            prototype_structure.effective_background_of("title-node", colors_inventory).color_id,
            "color-1",
        )
        self.assertEqual(
            prototype_structure.effective_color_of("title-node", colors_inventory).color_id,
            "color-2",
        )

    def test_color_usage_catalog_is_derived_outside_prototype_structure(self) -> None:
        prototype_structure = PrototypeStructure.build(_sample_elements())

        colors_inventory = build_color_usage_catalog(
            prototype_structure,
            existing_inventory=_sample_colors(),
        )

        self.assertIsNotNone(colors_inventory.entry_by_id("color-1"))
        self.assertIsNotNone(colors_inventory.entry_by_id("color-2"))
        self.assertEqual(colors_inventory.entry_by_value("rgb(20, 20, 20)").color_id, "color-2")

    def test_prototype_structure_does_not_import_color_catalog(self) -> None:
        source = Path("engine/domain/models/prototype_structure.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_imports = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "engine.domain.models.color"
            for alias in node.names
            if alias.name == "ColorCatalog"
        ]

        self.assertEqual(forbidden_imports, [])

    def test_excluded_pixel_boxes_use_html_scope_enums(self) -> None:
        prototype_structure = PrototypeStructure.build(
            (
                Element.build(
                    {
                        "node_id": "body-node",
                        "backend_node_id": 1,
                        "document_order": 1,
                        "children_ids": ["image-node"],
                        "tag_name": "body",
                        "node_name": "BODY",
                        "width": 240,
                        "height": 160,
                        "left": 0,
                        "top": 0,
                        "right": 240,
                        "bottom": 160,
                        "is_visible": True,
                        "properties": [],
                    }
                ),
                Element.build(
                    {
                        "node_id": "image-node",
                        "backend_node_id": 2,
                        "document_order": 2,
                        "parent_id": "body-node",
                        "children_ids": [],
                        "tag_name": "img",
                        "node_name": "IMG",
                        "x": 16,
                        "y": 24,
                        "width": 80,
                        "height": 60,
                        "left": 16,
                        "top": 24,
                        "right": 96,
                        "bottom": 84,
                        "is_visible": True,
                        "is_leaf": True,
                        "properties": [],
                    }
                ),
                Element.build(
                    {
                        "node_id": "hidden-video",
                        "backend_node_id": 3,
                        "document_order": 3,
                        "children_ids": [],
                        "tag_name": "video",
                        "node_name": "VIDEO",
                        "left": 100,
                        "top": 100,
                        "right": 150,
                        "bottom": 150,
                        "is_visible": False,
                        "properties": [],
                    }
                ),
                Element.build(
                    {
                        "node_id": "unknown-node",
                        "backend_node_id": 4,
                        "document_order": 4,
                        "children_ids": [],
                        "tag_name": "custom-card",
                        "node_name": "CUSTOM-CARD",
                        "left": 120,
                        "top": 120,
                        "right": 180,
                        "bottom": 180,
                        "is_visible": True,
                        "properties": [],
                    }
                ),
            )
        )

        self.assertEqual(
            prototype_structure.excluded_pixel_boxes(),
            ((16, 24, 96, 84),),
        )

    def test_build_color_scheme_sets_canonical_scheme_branches(self) -> None:
        prototype_structure = PrototypeStructure.build(_sample_elements())

        with tempfile.TemporaryDirectory() as tmp_dir:
            context = PipelineContext(file=None)
            context.set("prototype_structure", prototype_structure)
            context.set(
                "color.catalog",
                build_color_usage_catalog(
                    prototype_structure,
                    existing_inventory=_sample_colors(),
                ),
            )
            session = _build_session(Path(tmp_dir))
            context.set("session", session)
            with patch(
                "engine.pipeline.stages.build_color_scheme.build_color_histograms"
            ) as histogram_mock:
                histogram_mock.return_value = {
                    "environmental": [{"color": [255, 255, 255], "count": 12}],
                    "scheme": [{"color": [255, 255, 255], "count": 12}],
                }
                run_build_color_scheme_stage(context)
            self.assertTrue(context.has("scheme.colors"))
            self.assertTrue(all(isinstance(color, Color) for color in context.get("scheme.colors")))
            self.assertTrue(context.has("scheme.tonal_palettes"))
            self.assertTrue(Path(session.palette_preview_path).exists())

        self.assertFalse(context.has("scheme.color_scheme"))
        self.assertEqual(
            context.get("environmental.before.color_histogram"),
            [{"color": [255, 255, 255], "count": 12}],
        )
        self.assertEqual(
            context.get("scheme.color_histogram"),
            [{"color": [255, 255, 255], "count": 12}],
        )
        self.assertTrue(context.has("scheme.named_color_breakdown"))
        self.assertFalse(context.has("scheme." + "pixel_count"))
        self.assertFalse(context.has("scheme." + "residual" + "_pixel_count"))

    def test_effect_colors_payload_reads_from_prototype_structure(self) -> None:
        prototype_structure = PrototypeStructure.build(_sample_elements())
        colors_inventory = ColorCatalog.build(_sample_colors())

        payload = _effect_colors_payload(prototype_structure, colors_inventory)

        self.assertEqual(payload["count"], 1)
        effect_entry = payload["entries"][0]
        self.assertEqual(effect_entry["element_id"], "title-node")
        self.assertEqual(effect_entry["property_name"], "box-shadow")
        self.assertEqual(effect_entry["colors"][0]["color_id"], "color-3")
        self.assertEqual(effect_entry["colors"][0]["hex"], "#00000033")

    def test_build_contrast_report_reads_from_prototype_structure(self) -> None:
        prototype_structure = PrototypeStructure.build(_sample_elements())

        with tempfile.TemporaryDirectory() as tmp_dir:
            context = PipelineContext(file=None)
            context.set("prototype_structure", prototype_structure)
            context.set("scheme.colors", tuple(ColorCatalog.build(_sample_colors())))
            context.set("derived.raw_css_overview", _sample_contrast_css_overview())
            run_build_contrast_report_stage(context)

        report = context.get("derived.contrast_report")
        self.assertEqual(len(report), 1)
        issue = next(iter(report))
        self.assertEqual(issue.element_id, "title-node")
        self.assertEqual(issue.foreground.color_id, "color-2")
        self.assertEqual(issue.foreground.element_id, "title-node")
        self.assertEqual(issue.background.color_id, "color-1")
        self.assertEqual(issue.background.element_id, "body-node")
        self.assertEqual(issue.background_validation, "match")
