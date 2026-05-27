from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.enums.scope.css_properties import CSS_PROPERTIES
from engine.domain.enums.scope.html_elements import HTML_ELEMENTS_BY_ID
from engine.domain.enums.scope.context_keys import ContextKey
from engine.domain.models.color import Color
from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.element import Element, Property
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
from engine.pipeline.stages.capture_original_state import run_stage


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

        self.assertIs(child.parent, root)
        self.assertEqual([item.tag_name for item in root.iter_dfs()], ["body", "h1", "#text"])
        self.assertEqual([item.tag_name for item in root.iter_bfs()], ["body", "h1", "#text"])
        self.assertIs(root.find(lambda item: item.node_type == 3), text)
        self.assertEqual(root.filter(lambda item: item.tag_name == "h1"), (child,))

    def test_property_keeps_color_values_without_generated_ids(self) -> None:
        prop = Property(
            name="background-image",
            value="linear-gradient(rgb(255, 0, 0), #0000ff)",
        )

        self.assertEqual(
            prop.colors,
            (
                Color(0, 0, 255),
                Color(255, 0, 0),
            ),
        )
        payload = prop.to_dict()
        self.assertIn("colors", payload)
        self.assertNotIn("color_id", payload)
        self.assertNotIn("color_ids", payload)

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

            def capture_full_page_screenshot(self, *, output_path: Path) -> str:
                self.screenshot_path = str(output_path)
                return self.screenshot_path

            def extract_raw_snapshot(self, whitelist_styles: list[str]) -> dict[str, object]:
                background_index = whitelist_styles.index("background-color")
                color_index = whitelist_styles.index("color")
                styles = [[-1] * len(whitelist_styles), [-1] * len(whitelist_styles)]
                styles[0][background_index] = 6
                styles[1][color_index] = 7
                return {
                    "strings": ["#document", "html", "body", "h1", "#text", "", "rgb(255, 255, 255)", "rgb(20, 20, 20)"],
                    "documents": [
                        {
                            "nodes": {
                                "nodeName": [0, 1, 2, 3, 4],
                                "nodeType": [9, 1, 1, 1, 3],
                                "backendNodeId": [10, 11, 12, 13, 14],
                                "parentIndex": [-1, 0, 1, 2, 3],
                                "nodeValue": [5, 5, 5, 5, 5],
                            },
                            "layout": {
                                "nodeIndex": [2, 3],
                                "bounds": [[0, 0, 800, 600], [10, 20, 120, 32]],
                                "styles": styles,
                            },
                            "textBoxes": {"layoutIndex": [1]},
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
        metadata = context.get(ContextKey.DERIVED_RAW_SNAPSHOT_METADATA)

        self.assertIsInstance(dom_tree, Element)
        self.assertIsInstance(color_scheme, ColorScheme)
        self.assertEqual(metadata["node_count"], 5)
        self.assertEqual(len(color_scheme.colors), 2)
        self.assertEqual(dom_tree.find(lambda item: item.tag_name == "h1").is_text_node, True)
        self.assertNotIn("prototype_structure", context.snapshot())

    def test_page_builder_exposes_minimal_capture_contract(self) -> None:
        for name in (
            "new_from_file",
            "load_page",
            "extract_raw_snapshot",
            "get_full_document_node",
            "capture_full_page_screenshot",
            "close",
        ):
            self.assertTrue(hasattr(PageBuilder, name), msg=name)

    def test_scope_inventories_are_read_only(self) -> None:
        self.assertIsInstance(CSS_PROPERTIES, MappingProxyType)
        self.assertIsInstance(HTML_ELEMENTS_BY_ID, MappingProxyType)
        with self.assertRaises(TypeError):
            HTML_ELEMENTS_BY_ID["x-test"] = object()  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
