from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.adapters.browser.render_models import RenderSnapshot
from engine.domain.models.color import Color, ColorCatalog
from engine.domain.models.color_scheme import ColorScheme, TonalPalette
from engine.domain.models.element import Element, Property
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.quality_reports import ColorUsages
from engine.domain.models.session import Session
from engine.domain.models.style import StyleCatalog
from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.assemble_results import _effect_colors_payload
from engine.pipeline.stages.build_color_scheme import run_stage as run_build_color_scheme_stage
from engine.pipeline.stages.build_contrast_report import run_stage as run_build_contrast_report_stage
from engine.pipeline.stages.capture_original_state import run_stage as run_capture_original_state_stage


def _build_session(
    base_dir: Path,
    *,
    html_content: str = "<html></html>",
) -> Session:
    del base_dir
    session = Session()
    for directory in ("before", "after", "artifacts"):
        session.get_area_root(directory).mkdir(parents=True, exist_ok=True)
    before_html = session.get_area_root("before") / "index.html"
    after_html = session.get_area_root("after") / "index.html"
    before_html.write_text(
        html_content,
        encoding="utf-8",
    )
    after_html.write_text(
        html_content,
        encoding="utf-8",
    )
    session.save_in_before(before_html)
    session.save_in_after(after_html)
    return session


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
    return _build_color_catalog(
        (
            {"color_id": "color-1", "value": "rgb(255, 255, 255)", "usage_count": 1},
            {"color_id": "color-2", "value": "rgb(20, 20, 20)", "usage_count": 1},
            {"color_id": "color-3", "value": "rgba(0, 0, 0, 0.2)", "usage_count": 1},
        )
    )


def _build_color_catalog(entries) -> ColorCatalog:
    if isinstance(entries, ColorCatalog):
        return entries

    colors: list[Color] = []
    for index, item in enumerate(entries or (), start=1):
        if isinstance(item, Color):
            colors.append(item)
            continue
        color = Color.from_rgb(
            color_id=str(item.get("color_id") or f"color-{index}"),
            rgb_value=str(item.get("rgb_value") or item.get("value") or "rgb(0, 0, 0)"),
        )
        usage_count = int(item.get("element_usage_count") or item.get("usage_count") or 0)
        if usage_count > 0:
            color.element_usage_count = usage_count
        pixel_count = int(item.get("pixel_count") or 0)
        pixel_percentage = float(item.get("pixel_percentage") or 0.0)
        if pixel_count > 0 or pixel_percentage > 0.0:
            color.set_pixel_count(pixel_count, pixel_percentage)
        palette_id = item.get("palette_id") or item.get("mapped_palette_id")
        tone = item.get("tone") or item.get("mapped_tone")
        if palette_id is not None and tone is not None:
            color.set_palette_mapping(palette_id=str(palette_id), tone=int(tone))
        token = item.get("token")
        token_ids = item.get("token_ids") or ()
        if token:
            color.set_token_assignment(str(token))
        elif token_ids:
            color.set_token_assignment(str(next(iter(token_ids))))
        colors.append(color)
    return ColorCatalog(colors=tuple(colors))


def _build_current_color_catalog(prototype_structure: PrototypeStructure) -> ColorCatalog:
    color_catalog = ColorCatalog()
    for element in prototype_structure:
        for property_model in element.properties:
            color_ids: list[str] = []
            for color_value in property_model.color_values():
                color_ids.append(color_catalog.add_color(color_value))
            property_model.set_color_ids(color_ids)
    return color_catalog


class PrototypeStructureTests(unittest.TestCase):
    def test_pipeline_context_accepts_prototype_structure_root(self) -> None:
        context = PipelineContext()
        prototype_structure = PrototypeStructure.build(_sample_elements())
        context.set("prototype_structure", prototype_structure)
        self.assertIs(context.get("prototype_structure"), prototype_structure)

    def test_capture_original_state_populates_canonical_nodes(self) -> None:
        snapshot = RenderSnapshot(
            metadata={"nodeCount": 2},
            document={},
            nodes=_sample_elements(),
        )

        class FakePageBuilder:
            def __init__(self) -> None:
                self.screenshot_paths: list[str] = []

            def capture_full_page_screenshot(self, *, output_path: str) -> str:
                self.screenshot_paths.append(output_path)
                return output_path

            def capture_snapshot_models(self) -> tuple[RenderSnapshot, StyleCatalog]:
                return snapshot, StyleCatalog()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            page_builder = FakePageBuilder()
            context = PipelineContext()
            session = _build_session(tmp_path)
            context.set("session", session)
            context.set("page_builder", page_builder)
            run_capture_original_state_stage(context)

        prototype_structure = context.get("prototype_structure")
        self.assertIsInstance(prototype_structure, PrototypeStructure)
        self.assertTrue(context.has("style.catalog"))
        self.assertTrue(context.has("color.catalog"))
        self.assertTrue(context.has("derived.color_usages"))
        self.assertFalse(context.has("derived.raw_css_overview"))
        self.assertTrue(context.has("derived.raw_snapshot_metadata"))
        self.assertFalse(context.has("session.before_capture"))
        self.assertEqual(page_builder.screenshot_paths[0], session.get_path("before.png", "artifacts", "png"))
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

    def test_color_usages_groups_colors_by_current_buckets(self) -> None:
        usages = ColorUsages()

        for color_id, property_name in (
            ("color-background", "background-color"),
            ("color-background-image", "background-image"),
            ("color-border", "border-top-color"),
            ("color-outline", "outline-color"),
            ("color-decoration", "text-decoration-color"),
            ("color-shadow", "box-shadow"),
            ("color-filter", "filter"),
            ("color-typography", "color"),
            ("color-fill", "fill"),
            ("color-stroke", "stroke"),
        ):
            usages.add(color_id=color_id, property_name=property_name, element_id="node-1")
            usages.add(color_id=color_id, property_name=property_name, element_id="node-2")

        self.assertEqual(usages.background, ("color-background", "color-background-image"))
        self.assertEqual(usages.border, ("color-border", "color-outline"))
        self.assertEqual(usages.decoration, ("color-decoration", "color-shadow", "color-filter"))
        self.assertEqual(usages.typography, ("color-typography",))
        self.assertEqual(usages.other, ("color-fill", "color-stroke"))
        self.assertEqual(
            usages.to_dict(),
            {
                "background": ["color-background", "color-background-image"],
                "border": ["color-border", "color-outline"],
                "decoration": ["color-decoration", "color-shadow", "color-filter"],
                "typography": ["color-typography"],
                "other": ["color-fill", "color-stroke"],
            },
        )

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

        colors_inventory = _build_current_color_catalog(prototype_structure)

        self.assertIsNotNone(colors_inventory.entry_by_id("color-1"))
        self.assertIsNotNone(colors_inventory.entry_by_id("color-2"))
        self.assertEqual(colors_inventory.entry_by_value("rgb(20, 20, 20)").color_id, "color-2")

    def test_property_preserves_multiple_color_ids_in_original_order(self) -> None:
        prototype_structure = PrototypeStructure.build(
            (
                Element.build(
                    {
                        "node_id": "gradient-node",
                        "backend_node_id": 1,
                        "document_order": 1,
                        "children_ids": [],
                        "tag_name": "div",
                        "node_name": "DIV",
                        "is_visible": True,
                        "properties": [
                            {
                                "name": "background-image",
                                "value": "linear-gradient(rgb(255, 0, 0), rgb(0, 0, 255))",
                            }
                        ],
                    }
                ),
            )
        )

        colors_inventory = _build_current_color_catalog(prototype_structure)
        property_model = prototype_structure.node_by_id("gradient-node").properties[0]  # type: ignore[union-attr]

        self.assertIsNone(property_model.color_id)
        self.assertEqual(property_model.color_ids, ("color-1", "color-2"))
        self.assertEqual(colors_inventory.entry_by_id("color-1").rgb_value, "rgb(255, 0, 0)")
        self.assertEqual(colors_inventory.entry_by_id("color-2").rgb_value, "rgb(0, 0, 255)")

    def test_color_catalog_enrichment_preserves_existing_metadata(self) -> None:
        colors_inventory = _sample_colors()
        entry = colors_inventory.entry_by_id("color-1")
        entry.set_token_assignment("token-color-1")  # type: ignore[union-attr]
        entry.set_pixel_count(42, 12.5)  # type: ignore[union-attr]
        entry.set_palette_mapping(  # type: ignore[union-attr]
            palette_id="palette-achromatic-1",
            tone=90,
        )

        self.assertEqual(entry.pixel_count, 42)
        self.assertEqual(entry.pixel_percentage, 12.5)
        self.assertEqual(entry.palette_id, "palette-achromatic-1")
        self.assertEqual(entry.tone, 90)
        self.assertEqual(entry.token, "token-color-1")
        self.assertEqual(tuple(color.color_id for color in colors_inventory), ("color-1", "color-2", "color-3"))

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
            context = PipelineContext()
            context.set("prototype_structure", prototype_structure)
            context.set(
                "color.catalog",
                _build_current_color_catalog(prototype_structure),
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
            self.assertFalse(context.has("scheme." + "colors"))
            colors = context.get("color.catalog")
            self.assertTrue(all(isinstance(color, Color) for color in colors))
            self.assertEqual(colors.entry_by_id("color-1").pixel_count, 12)
            self.assertEqual(colors.entry_by_id("color-1").pixel_percentage, 100.0)
            self.assertTrue(
                any(color.palette_id is not None for color in colors)
            )
            self.assertTrue(context.has("scheme.tonal_palettes"))
            self.assertTrue(session.get_path("palette_preview.png", "artifacts", "png").exists())

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
        colors_inventory = _sample_colors()

        payload = _effect_colors_payload(prototype_structure, colors_inventory)

        self.assertEqual(payload["count"], 1)
        effect_entry = payload["entries"][0]
        self.assertEqual(effect_entry["element_id"], "title-node")
        self.assertEqual(effect_entry["property_name"], "box-shadow")
        self.assertEqual(effect_entry["colors"][0]["color_id"], "color-3")
        self.assertEqual(effect_entry["colors"][0]["hex"], "#00000033")

    def test_build_contrast_report_reads_from_prototype_structure(self) -> None:
        prototype_structure = PrototypeStructure.build(
            (
                Element.build(
                    {
                        "node_id": "body-node",
                        "backend_node_id": 1,
                        "document_order": 1,
                        "children_ids": ["muted-node"],
                        "tag_name": "body",
                        "node_name": "BODY",
                        "is_visible": True,
                        "effective_background": "rgb(255, 255, 255)",
                        "properties": [
                            {
                                "name": "background-color",
                                "value": "rgb(255, 255, 255)",
                                "color_id": "color-1",
                            }
                        ],
                    }
                ),
                Element.build(
                    {
                        "node_id": "muted-node",
                        "backend_node_id": 2,
                        "parent_id": "body-node",
                        "document_order": 2,
                        "children_ids": [],
                        "tag_name": "p",
                        "node_name": "P",
                        "selector": "p.muted",
                        "text": "Muted text",
                        "is_visible": True,
                        "x": 12,
                        "y": 24,
                        "width": 160,
                        "height": 32,
                        "properties": [
                            {
                                "name": "color",
                                "value": "rgb(180, 180, 180)",
                                "color_id": "color-2",
                            }
                        ],
                    }
                ),
            )
        )
        colors_inventory = _build_color_catalog(
            (
                {"color_id": "color-1", "value": "rgb(255, 255, 255)", "usage_count": 1},
                {"color_id": "color-2", "value": "rgb(180, 180, 180)", "usage_count": 1},
            )
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            context = PipelineContext()
            context.set("prototype_structure", prototype_structure)
            context.set("color.catalog", colors_inventory)
            run_build_contrast_report_stage(context)

        report = context.get("derived.contrast_report")
        self.assertEqual(len(report), 1)
        issue = next(iter(report))
        self.assertEqual(issue.element_id, "muted-node")
        self.assertEqual(issue.foreground.color_id, "color-2")
        self.assertEqual(issue.foreground.element_id, "muted-node")
        self.assertEqual(issue.background.color_id, "color-1")
        self.assertEqual(issue.background.element_id, "body-node")
        self.assertEqual(issue.background_validation, "model")
        payload = issue.to_dict()
        self.assertNotIn("style_id", payload["foreground"])
        self.assertNotIn("declaration_id", payload["foreground"])
        self.assertNotIn("property_name", payload["foreground"])
        self.assertNotIn("declared_property", payload["foreground"])
        self.assertNotIn("style_id", payload["background"])
        self.assertNotIn("declaration_id", payload["background"])
        self.assertNotIn("property_name", payload["background"])
        self.assertNotIn("declared_property", payload["background"])

    def test_build_contrast_report_uses_text_node_target_with_parent_styles(self) -> None:
        prototype_structure = PrototypeStructure.build(
            (
                Element.build(
                    {
                        "node_id": "body-node",
                        "backend_node_id": 1,
                        "document_order": 1,
                        "children_ids": ["label-node"],
                        "tag_name": "body",
                        "node_name": "BODY",
                        "is_visible": True,
                        "properties": [
                            {
                                "name": "background-color",
                                "value": "rgb(255, 255, 255)",
                                "color_id": "color-1",
                            }
                        ],
                    }
                ),
                Element.build(
                    {
                        "node_id": "label-node",
                        "backend_node_id": 2,
                        "parent_id": "body-node",
                        "document_order": 2,
                        "children_ids": ["label-text"],
                        "tag_name": "span",
                        "node_name": "SPAN",
                        "selector": "span.label",
                        "text": "Muted text",
                        "is_visible": True,
                        "properties": [
                            {
                                "name": "color",
                                "value": "rgb(180, 180, 180)",
                                "color_id": "color-2",
                            }
                        ],
                    }
                ),
                Element.build(
                    {
                        "node_id": "label-text",
                        "backend_node_id": 3,
                        "parent_id": "label-node",
                        "document_order": 3,
                        "children_ids": [],
                        "tag_name": "#text",
                        "node_name": "#text",
                        "xpath": "/html[1]/body[1]/span[1]/text()[1]",
                        "text": "Muted text",
                        "is_visible": True,
                        "is_text_node": True,
                        "x": 4,
                        "y": 8,
                        "width": 90,
                        "height": 18,
                    }
                ),
            )
        )
        colors_inventory = _build_color_catalog(
            (
                {"color_id": "color-1", "value": "rgb(255, 255, 255)", "usage_count": 1},
                {"color_id": "color-2", "value": "rgb(180, 180, 180)", "usage_count": 1},
            )
        )

        context = PipelineContext()
        context.set("prototype_structure", prototype_structure)
        context.set("color.catalog", colors_inventory)
        run_build_contrast_report_stage(context)

        report = context.get("derived.contrast_report")
        self.assertEqual(len(report), 1)
        issue = next(iter(report))
        self.assertEqual(issue.element_id, "label-text")
        self.assertEqual(issue.selector, "/html[1]/body[1]/span[1]/text()[1]")
        self.assertEqual(issue.foreground.element_id, "label-node")
        self.assertEqual(issue.background.element_id, "body-node")

    def test_build_contrast_report_skips_text_without_resolved_background(self) -> None:
        prototype_structure = PrototypeStructure.build(
            (
                Element.build(
                    {
                        "node_id": "text-node",
                        "backend_node_id": 1,
                        "document_order": 1,
                        "children_ids": [],
                        "tag_name": "p",
                        "node_name": "P",
                        "text": "Muted text",
                        "is_visible": True,
                        "properties": [
                            {
                                "name": "color",
                                "value": "rgb(180, 180, 180)",
                                "color_id": "color-2",
                            }
                        ],
                    }
                ),
            )
        )
        colors_inventory = _build_color_catalog(
            ({"color_id": "color-2", "value": "rgb(180, 180, 180)", "usage_count": 1},)
        )

        context = PipelineContext()
        context.set("prototype_structure", prototype_structure)
        context.set("color.catalog", colors_inventory)
        run_build_contrast_report_stage(context)

        self.assertEqual(len(context.get("derived.contrast_report")), 0)

