import unittest

from flask import Flask, g

from engine.domain.data.scope_css import CSSPROPERTIES
from engine.domain.models.element import DomTree, Element, Property
from engine.domain.models.style import StyleSource, Styles
from engine.pipeline.stages.capture_original_state import (
    _filter_properties,
    process_dom_snapshot,
)


class FakePageBuilder:
    viewport_size = {"width": 800, "height": 600}

    def __init__(self, snapshot, document_root):
        self._snapshot = snapshot
        self._document_root = document_root

    @property
    def document_root(self):
        return self._document_root

    def extract_raw_snapshot(self, _whitelist_styles):
        return self._snapshot

    def get_box_model(self, _backend_node_id):
        return {
            "width": 10.0,
            "height": 10.0,
            "content": [],
            "padding": [],
            "border": [],
            "margin": [],
        }


class CaptureOriginalStateDomTreeTest(unittest.TestCase):
    def test_process_dom_snapshot_builds_dom_tree(self):
        app = Flask(__name__)
        whitelist_styles = list(CSSPROPERTIES.keys())
        background_index = whitelist_styles.index("background-color")
        color_index = whitelist_styles.index("color")
        body_styles = [-1] * len(whitelist_styles)
        image_styles = [-1] * len(whitelist_styles)
        body_styles[background_index] = 15
        image_styles[color_index] = 16

        snapshot = {
            "strings": [
                "#document",
                "HTML",
                "HEAD",
                "META",
                "BODY",
                "IMG",
                "src",
                "Assets/Icon.SVG",
                "name",
                "color-scheme",
                "content",
                "light dark",
                "",
                "DIV",
                "data-theme",
                "transparent",
                "rgb(255, 0, 0)",
            ],
            "documents": [
                {
                    "nodes": {
                        "backendNodeId": [1, 2, 3, 4, 5, 6, 7],
                        "parentIndex": [-1, 0, 1, 2, 1, 4, 4],
                        "nodeName": [0, 1, 2, 3, 4, 5, 13],
                        "nodeType": [9, 1, 1, 1, 1, 1, 1],
                        "nodeValue": [12, 12, 12, 12, 12, 12, 12],
                        "attributes": [
                            [],
                            [],
                            [],
                            [8, 9, 10, 11],
                            [],
                            [6, 7],
                            [14, 9],
                        ],
                    },
                    "layout": {
                        "nodeIndex": [4, 5],
                        "styles": [body_styles, image_styles],
                    },
                }
            ],
        }
        document_root = {
            "backendNodeId": 1,
            "nodeId": 101,
            "nodeName": "#document",
            "children": [
                {
                    "backendNodeId": 2,
                    "nodeId": 102,
                    "nodeName": "HTML",
                    "children": [
                        {
                            "backendNodeId": 3,
                            "nodeId": 103,
                            "nodeName": "HEAD",
                            "children": [
                                {
                                    "backendNodeId": 4,
                                    "nodeId": 104,
                                    "nodeName": "META",
                                }
                            ],
                        },
                        {
                            "backendNodeId": 5,
                            "nodeId": 105,
                            "nodeName": "BODY",
                            "children": [
                                {
                                    "backendNodeId": 6,
                                    "nodeId": 106,
                                    "nodeName": "IMG",
                                },
                                {
                                    "backendNodeId": 7,
                                    "nodeId": 107,
                                    "nodeName": "DIV",
                                },
                            ],
                        },
                    ],
                }
            ],
        }

        with app.app_context():
            g.dom_tree = DomTree()
            g.style = Styles()
            g.page_builder = FakePageBuilder(snapshot, document_root)

            process_dom_snapshot.fn()

            self.assertEqual("html", g.dom_tree.html.tag_name)
            self.assertEqual("body", g.dom_tree.body.tag_name)
            self.assertEqual(800, g.dom_tree.page_width)
            self.assertEqual(600, g.dom_tree.page_height)
            self.assertEqual(106, g.dom_tree.elements[6].node_id)
            self.assertIs(g.dom_tree.elements[5], g.dom_tree.elements[6].parent)
            self.assertEqual(
                "Assets/Icon.SVG",
                g.dom_tree.elements[6].image_references[0].before_value,
            )
            self.assertEqual(
                "rgb(255, 0, 0)",
                g.dom_tree.elements[6].property("color")["before_value"],
            )
            self.assertFalse(set(g.dom_tree.elements) - {
                element.backend_node_id
                for element in g.dom_tree.html.iter_dfs()
            })

    def test_filter_properties_marks_registered_sources_as_defined(self):
        element = Element(
            backend_node_id=1,
            node_id=101,
            tag_name="p",
            category="text",
            node_type=1,
            properties=[
                Property(
                    name="color",
                    before_value="rgb(255, 0, 0)",
                ),
            ],
        )

        _filter_properties(
            element,
            {
                "color": [
                    StyleSource(
                        target_property="color",
                        declaration_name="color",
                        value="red",
                        source_type="rule",
                        origin="regular",
                    )
                ]
            },
        )

        self.assertEqual("matched", element.properties[0].type)
        self.assertTrue(element.properties[0].is_defined)

    def test_filter_properties_keeps_asset_references(self):
        element = Element(
            backend_node_id=1,
            node_id=101,
            tag_name="div",
            category="container",
            node_type=1,
            properties=[
                Property(
                    name="background-image",
                    before_value='url("imagenes/icono-de-prueba.svg")',
                ),
            ],
        )

        element.image_references.append(element.properties.pop())
        _filter_properties(element, {})

        self.assertEqual(0, len(element.properties))
        self.assertEqual(1, len(element.image_references))
        self.assertEqual("background-image", element.image_references[0].name)


if __name__ == "__main__":
    unittest.main()
