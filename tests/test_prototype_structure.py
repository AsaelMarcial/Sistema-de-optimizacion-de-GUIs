from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

import numpy as np

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.enums.scope.css_properties import (
    CSS_PROPERTIES,
    DEFAULT_VALUE,
    SHORTHAND,
    getAllPropertyNames,
)
from engine.domain.enums.scope.html_elements import HTML_ELEMENTS_BY_ID
from engine.domain.enums.scope.context_keys import ContextKey
from engine.domain.models.color_scheme import Color, ColorScheme
from engine.domain.models.element import Element, Property
from engine.domain.models.summary import ContrastIssue, Summary
from engine.domain.models.session import Session
from engine.domain.utils.parsers import (
    attr_equals,
    flatten_list,
    get_value,
    resolve_index_map,
    resolve_pairs,
    resolve_value,
)
from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.capture_original_state import _collapse_redundant_border_colors
from engine.pipeline.stages.capture_original_state import _collapse_redundant_color_longhands
from engine.pipeline.stages.build_color_scheme import run_stage as run_build_color_scheme_stage
from engine.pipeline.stages.capture_original_state import run_stage
from engine.pipeline.stages.data_processor import run_stage as run_data_processor_stage


def _session_with_html() -> Session:
    session = Session()
    for area in ("before", "after", "artifacts"):
        session.get_area_root(area).mkdir(parents=True, exist_ok=True)
    source = session.get_area_root("before") / "index.html"
    source.write_text("<html><body><h1>Title</h1></body></html>", encoding="utf-8")
    session.save_in_before(source)
    return session


class CoreDomAndColorTests(unittest.TestCase):
    def test_element_builds_tree_and_traverses(self) -> None:
        root = Element(backend_node_id=1, node_id=1, tag_name="body", node_type=1)
        child = Element(backend_node_id=2, node_id=2, tag_name="h1", node_type=1)
        text = Element(backend_node_id=3, node_id=3, tag_name="#text", node_type=3)

        root.add_child(child)
        child.add_child(text)

        self.assertEqual(child.parent_backend_node_id, root.backend_node_id)
        self.assertEqual([item.tag_name for item in root.iter_dfs()], ["#text", "h1", "body"])
        self.assertEqual([item.tag_name for item in root.iter_bfs()], ["body", "h1", "#text"])
        self.assertIs(root.find(lambda item: item.node_type == 3), text)
        self.assertEqual(root.filter(lambda item: item.tag_name == "h1"), (child,))
        self.assertIs(root.property("color"), None)
        child.properties.append(Property("color", "rgb(0, 0, 0)", has_color=True))
        self.assertEqual(child.property("color").value, "rgb(0, 0, 0)")
        self.assertTrue(root.has_tag("body"))

    def test_property_marks_color_values_without_generated_ids(self) -> None:
        prop = Property(
            name="background-image",
            value="linear-gradient(rgb(255, 0, 0), #0000ff)",
            has_color=True,
        )

        self.assertTrue(prop.has_color)
        element = Element(backend_node_id=1, node_id=1, tag_name="div", node_type=1)
        element.properties.append(prop)
        self.assertEqual(
            element.property_values(),
            (("background-image", "linear-gradient(rgb(255, 0, 0), #0000ff)"),),
        )

    def test_border_color_longhands_are_collapsed_only_when_redundant(self) -> None:
        element = Element(backend_node_id=1, node_id=1, tag_name="div", node_type=1)
        element.properties.extend(
            [
                Property("border", "1px solid rgb(255, 0, 0)", has_color=True),
                Property("border-color", "rgb(255, 0, 0)", has_color=True),
                Property("border-left-color", "rgb(0, 0, 255)", has_color=True),
            ]
        )

        _collapse_redundant_border_colors(element)

        self.assertEqual(
            element.property_values(),
            (
                ("border", "1px solid rgb(255, 0, 0)"),
                ("border-left-color", "rgb(0, 0, 255)"),
            ),
        )

    def test_similar_color_longhands_are_collapsed_only_when_redundant(self) -> None:
        element = Element(backend_node_id=1, node_id=1, tag_name="div", node_type=1)
        element.properties.extend(
            [
                Property("outline", "2px solid rgb(10, 10, 10)", has_color=True),
                Property("outline-color", "rgb(10, 10, 10)", has_color=True),
                Property("border-top", "1px solid rgb(70, 70, 70)", has_color=True),
                Property("border-top-color", "rgb(70, 70, 70)", has_color=True),
                Property("column-rule", "1px solid rgb(20, 20, 20)", has_color=True),
                Property("column-rule-color", "rgb(30, 30, 30)", has_color=True),
                Property("text-decoration", "underline rgb(40, 40, 40)", has_color=True),
                Property("text-decoration-color", "rgb(40, 40, 40)", has_color=True),
                Property("text-emphasis", "circle rgb(50, 50, 50)", has_color=True),
                Property("text-emphasis-color", "rgb(60, 60, 60)", has_color=True),
            ]
        )

        _collapse_redundant_color_longhands(element)

        self.assertEqual(
            element.property_values(),
            (
                ("outline", "2px solid rgb(10, 10, 10)"),
                ("border-top", "1px solid rgb(70, 70, 70)"),
                ("column-rule", "1px solid rgb(20, 20, 20)"),
                ("column-rule-color", "rgb(30, 30, 30)"),
                ("text-decoration", "underline rgb(40, 40, 40)"),
                ("text-emphasis", "circle rgb(50, 50, 50)"),
                ("text-emphasis-color", "rgb(60, 60, 60)"),
            ),
        )

    def test_generic_parsers_are_domain_agnostic(self) -> None:
        payload = {"items": [{"name": "a", "values": [1, [2, 3]]}]}

        self.assertEqual(resolve_value(payload, "items.0.name"), "a")
        self.assertEqual(get_value(payload["items"], 0)["name"], "a")
        self.assertEqual(list(flatten_list(payload["items"], ["name", "values"], depth=1)), [["a"], [1, 2, 3]])
        self.assertEqual(resolve_index_map(["x", "y"]), {"x": 0, "y": 1})
        self.assertEqual(list(resolve_pairs(["a", "b"], [1])), [("a", 1), ("b", None)])
        self.assertTrue(attr_equals("name", "a")(payload["items"][0]))

    def test_capture_original_state_produces_dom_tree_and_color_scheme(self) -> None:
        class FakePageBuilder:
            def __init__(self) -> None:
                self.screenshot_path = None

            def capture_fullpage_screenshot(self, *, output_path: Path) -> str:
                self.screenshot_path = str(output_path)
                return self.screenshot_path

            def resolve_backend_node_id(self, backend_node_id: int) -> int:
                return int(backend_node_id) + 1000

            def extract_raw_snapshot(self, whitelist_styles: list[str]) -> dict[str, object]:
                background_index = whitelist_styles.index("background-color")
                border_index = whitelist_styles.index("border")
                border_color_index = whitelist_styles.index("border-color")
                color_index = whitelist_styles.index("color")
                fill_opacity_index = whitelist_styles.index("fill-opacity")
                text_emphasis_index = whitelist_styles.index("text-emphasis")
                styles = [[-1] * len(whitelist_styles), [-1] * len(whitelist_styles)]
                styles[0][background_index] = 9
                styles[0][border_index] = 12
                styles[0][border_color_index] = 13
                styles[0][fill_opacity_index] = 14
                styles[0][text_emphasis_index] = 15
                styles[1][color_index] = 10
                return {
                    "strings": [
                        "#document",
                        "html",
                        "head",
                        "meta",
                        "title",
                        "body",
                        "h1",
                        "#text",
                        "",
                        "rgb(255, 255, 255)",
                        "rgb(20, 20, 20)",
                        "Title",
                        "0px none rgb(0, 0, 0)",
                        "rgb(0, 0, 0)",
                        "1",
                        "none rgb(0, 255, 255)",
                    ],
                    "documents": [
                        {
                            "nodes": {
                                "nodeName": [0, 1, 2, 3, 4, 5, 6, 7],
                                "nodeType": [9, 1, 1, 1, 1, 1, 1, 3],
                                "backendNodeId": [10, 11, 12, 13, 14, 15, 16, 17],
                                "parentIndex": [-1, 0, 1, 2, 2, 1, 5, 6],
                                "nodeValue": [8, 8, 8, 8, 8, 8, 8, 11],
                            },
                            "layout": {
                                "nodeIndex": [5, 6],
                                "bounds": [[0, 0, 800, 600], [10, 20, 120, 32]],
                                "styles": styles,
                            },
                        }
                    ],
                }

        context = PipelineContext()
        session = _session_with_html()
        fake_builder = FakePageBuilder()
        context.set(ContextKey.SESSION, session)
        context.set(ContextKey.PAGE_BUILDER, fake_builder)

        run_stage(context)

        dom_tree = context.get(ContextKey.DOM_TREE)
        color_scheme = context.get(ContextKey.COLOR_SCHEME)

        self.assertIsInstance(dom_tree, Element)
        self.assertIsInstance(color_scheme, ColorScheme)
        self.assertEqual(dom_tree.tag_name, "body")
        self.assertEqual(dom_tree.node_id, dom_tree.backend_node_id + 1000)
        self.assertEqual(dom_tree.parent_backend_node_id, -1)
        self.assertIsNone(dom_tree.find(lambda item: item.tag_name == "html"))
        self.assertIsNone(dom_tree.find(lambda item: item.tag_name == "head"))
        self.assertIsNone(dom_tree.find(lambda item: item.tag_name == "meta"))
        self.assertIsNone(dom_tree.find(lambda item: item.tag_name == "title"))
        self.assertEqual(len(color_scheme.colors), 2)
        self.assertFalse(dom_tree.find(lambda item: item.tag_name == "h1").is_text_node)
        body = dom_tree
        heading = dom_tree.find(lambda item: item.tag_name == "h1")
        text = dom_tree.find(lambda item: item.tag_name == "#text")
        self.assertEqual(heading.parent_backend_node_id, body.backend_node_id)
        self.assertEqual(heading.node_id, heading.backend_node_id + 1000)
        self.assertTrue(text.is_text_node)
        self.assertEqual(text.properties, [])
        self.assertEqual(body.property_values(), (("background-color", "rgb(255, 255, 255)"),))
        self.assertNotIn("border", dict(body.property_values()))
        self.assertNotIn("border-color", dict(body.property_values()))
        self.assertNotIn("fill-opacity", dict(body.property_values()))
        self.assertNotIn("text-emphasis", dict(body.property_values()))
        self.assertFalse(context.has("prototype_structure"))
        self.assertFalse(context.has("derived.raw_snapshot_metadata"))

    def test_build_color_scheme_reads_public_dom_properties(self) -> None:
        root = Element(backend_node_id=1, node_id=1, tag_name="body", node_type=1)
        root.properties.append(
            Property(
                name="background-color",
                value="rgb(255, 255, 255)",
                has_color=True,
            )
        )

        context = PipelineContext()
        session = _session_with_html()
        color_scheme = ColorScheme()
        color_scheme.add_color("rgb(255, 255, 255)")
        context.set(ContextKey.SESSION, session)
        context.set(ContextKey.DOM_TREE, root)
        context.set(ContextKey.COLOR_SCHEME, color_scheme)

        with patch(
            "engine.pipeline.stages.build_color_scheme.build_color_histograms",
            return_value={
                "environmental": [{"color": [255, 255, 255], "count": 1}],
                "scheme": [{"color": [255, 255, 255], "count": 1}],
            },
        ), patch("engine.pipeline.stages.build_color_scheme.render_palette_preview"):
            run_build_color_scheme_stage(context)

        self.assertEqual(len(context.get(ContextKey.COLOR_SCHEME).get_colors()), 1)
        self.assertGreaterEqual(len(context.get(ContextKey.COLOR_SCHEME).get_palettes()), 1)
        self.assertEqual(context.get(ContextKey.SCHEME_COLOR_HISTOGRAM), [{"color": [255, 255, 255], "count": 1}])

    def test_data_processor_builds_summary_overviews_and_contrast_issues(self) -> None:
        class FakePageBuilder:
            def resolve_backend_node_id(self, backend_node_id: int) -> int:
                return int(backend_node_id) + 1000

            def get_background_colors(self, node_id: int) -> dict[str, object]:
                if node_id == 1004:
                    return {
                        "background_colors": ["rgb(255, 255, 255)"],
                        "font_size": "12px",
                        "font_weight": "400",
                    }
                return {
                    "font_size": "12px",
                    "font_weight": "400",
                }

            def get_computed_styles_for_node(self, node_id: int) -> dict[str, str]:
                return {"color": "rgb(255, 0, 0)"}

            def get_box_model(self, backend_node_id: int) -> list[float]:
                return [0, 0, 5, 0, 5, 5, 0, 5]

        root = Element(backend_node_id=1, node_id=1001, tag_name="body", node_type=1)
        image = Element(
            backend_node_id=2,
            node_id=1002,
            tag_name="img",
            node_type=1,
            x=0,
            y=0,
            width=5,
            height=5,
        )
        text_ok = Element(backend_node_id=4, node_id=1004, tag_name="#text", node_type=3, is_text_node=True)
        text_warn = Element(backend_node_id=5, node_id=1005, tag_name="#text", node_type=3, is_text_node=True)
        root.add_child(image)
        root.add_child(text_ok)
        root.add_child(text_warn)

        color_scheme = ColorScheme()
        red = color_scheme.add_color("rgb(255, 0, 0)")
        black = color_scheme.add_color("rgb(0, 0, 0)")

        context = PipelineContext()
        context.set(ContextKey.SESSION, _session_with_html())
        context.set(ContextKey.PAGE_BUILDER, FakePageBuilder())
        context.set(ContextKey.DOM_TREE, root)
        context.set(ContextKey.COLOR_SCHEME, color_scheme)

        with patch(
            "engine.pipeline.stages.data_processor.build_histogram",
            side_effect=[
                [["rgb(255, 255, 255)", 100]],
                [["rgb(254, 0, 0)", 8], ["rgb(0, 0, 0)", 2]],
            ],
        ):
            run_data_processor_stage(context)

        summary = context.get(ContextKey.SUMMARY)
        distribution = summary.overview("colors_distribution").data

        self.assertIsInstance(summary, Summary)
        self.assertEqual(len(summary.contrast_issues), 1)
        self.assertEqual(summary.contrast_issues[0].backend_node_id, 4)
        self.assertTrue(any(warning.code == "background_colors_unavailable" for warning in summary.warnings))
        self.assertEqual(sum(item[1] for item in distribution), 10)
        self.assertEqual(distribution[0][1], 8)
        self.assertEqual(distribution[1][1], 2)

    def test_tonal_palette_colors_are_serialized_as_css_hex(self) -> None:
        color_scheme = ColorScheme()
        neutral = color_scheme.get_palette("Neutral")

        self.assertIsNotNone(neutral)
        self.assertEqual(neutral.tones[0].color.space(), "srgb")
        self.assertEqual(neutral.tones[0].color.to_string(hex=True), "#000000")

    def test_quality_reports_use_color_value_objects(self) -> None:
        summary = Summary()
        issue = summary.add_contrast_issue(
            issue_id=1,
            backend_node_id=13,
            contrast_ratio=2.4,
            required_ratio=4.5,
            is_large_text=False,
            foreground=Color("rgb(255, 0, 0)"),
            background=Color("rgb(255, 255, 255)"),
        )

        self.assertEqual(summary.contrast_issues[0], issue)
        self.assertEqual(summary.contrast_issues[0].foreground, Color("rgb(255, 0, 0)"))
        self.assertEqual(summary.contrast_issues[0].background, Color("rgb(255, 255, 255)"))

    def test_page_builder_exposes_minimal_capture_contract(self) -> None:
        for name in (
            "load_page",
            "extract_raw_snapshot",
            "get_full_document_node",
            "resolve_backend_node_id",
            "get_background_colors",
            "get_box_model",
            "get_computed_styles_for_node",
            "capture_fullpage_screenshot",
            "close",
        ):
            self.assertTrue(hasattr(PageBuilder, name), msg=name)

    def test_scope_inventories_are_read_only(self) -> None:
        self.assertIsInstance(CSS_PROPERTIES, MappingProxyType)
        self.assertIsInstance(HTML_ELEMENTS_BY_ID, MappingProxyType)
        self.assertNotIn("caret", getAllPropertyNames())
        self.assertNotIn("mask-border", getAllPropertyNames())
        self.assertNotIn("text-fill-color", getAllPropertyNames())
        for property_name in (
            "background",
            "border-top",
            "border-right",
            "border-bottom",
            "border-left",
            "border-image",
            "border-image-source",
            "filter",
            "text-shadow",
            "stroke",
            "stroke-width",
            "caret-color",
            "accent-color",
            "text-decoration",
            "text-decoration-color",
            "text-emphasis",
            "text-emphasis-color",
            "text-emphasis-style",
        ):
            self.assertIn(property_name, getAllPropertyNames())
        self.assertEqual(CSS_PROPERTIES["border-color"][SHORTHAND], "border")
        self.assertEqual(CSS_PROPERTIES["border-top-color"][SHORTHAND], "border-top")
        self.assertEqual(CSS_PROPERTIES["border-inline-end-color"][SHORTHAND], "border-inline-end")
        self.assertEqual(CSS_PROPERTIES["outline-color"][SHORTHAND], "outline")
        self.assertEqual(CSS_PROPERTIES["column-rule-color"][SHORTHAND], "column-rule")
        self.assertEqual(CSS_PROPERTIES["text-decoration-color"][SHORTHAND], "text-decoration")
        self.assertEqual(CSS_PROPERTIES["text-emphasis-color"][SHORTHAND], "text-emphasis")
        self.assertEqual(CSS_PROPERTIES["box-shadow"][DEFAULT_VALUE], ("none",))
        self.assertEqual(CSS_PROPERTIES["filter"][DEFAULT_VALUE], ("none",))
        self.assertEqual(CSS_PROPERTIES["fill-opacity"][DEFAULT_VALUE], ("1",))
        self.assertEqual(CSS_PROPERTIES["caret-color"][DEFAULT_VALUE], ("auto", "currentcolor", "rgb(0, 0, 0)"))
        self.assertEqual(CSS_PROPERTIES["flood-color"][DEFAULT_VALUE], ("rgb(0, 0, 0)",))
        self.assertEqual(CSS_PROPERTIES["lighting-color"][DEFAULT_VALUE], ("rgb(255, 255, 255)",))
        self.assertEqual(CSS_PROPERTIES["stop-color"][DEFAULT_VALUE], ("rgb(0, 0, 0)",))
        for property_name, property_data in CSS_PROPERTIES.items():
            if "text" in property_name:
                self.assertEqual(property_data["category"].value, "typography", msg=property_name)
                self.assertEqual(property_data["role"].value, "foreground", msg=property_name)
            if "stroke" in property_name:
                self.assertEqual(property_data["category"].value, "border", msg=property_name)
                self.assertEqual(property_data["role"].value, "foreground", msg=property_name)
            self.assertIn(DEFAULT_VALUE, property_data, msg=property_name)
        with self.assertRaises(TypeError):
            HTML_ELEMENTS_BY_ID["x-test"] = object()  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
