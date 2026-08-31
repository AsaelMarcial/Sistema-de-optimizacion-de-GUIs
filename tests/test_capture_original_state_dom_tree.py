import unittest

from engine.pipeline.stages.capture_original_state import (
    approve_elements,
    build_element_tree,
    _filter_properties,
)
from engine.domain.models.element import Element, Property


class FakePageBuilder:
    def __init__(self, document_root):
        self._document_root = document_root

    def get_full_document_node(self, *, refresh=False):
        return self._document_root

    def get_box_model(self, backend_node_id):
        return {
            "width": 10.0,
            "height": 10.0,
            "content": [],
            "padding": [],
            "border": [],
            "margin": [],
        }


class CaptureOriginalStateDomTreeTest(unittest.TestCase):
    def test_filter_properties_uses_hashable_color_signatures(self):
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

        _filter_properties(element, "color: rgb(255, 0, 0);")

        self.assertEqual("matched", element.properties[0].type)
        self.assertTrue(element.properties[0].is_defined)

    def test_approves_text_and_pseudo_nodes_without_orphan_html(self):
        text = {
            "backendNodeId": 7,
            "nodeId": 107,
            "nodeName": "#text",
            "nodeType": 3,
            "nodeValue": "Hello",
        }
        pseudo = {
            "backendNodeId": 8,
            "nodeId": 108,
            "nodeName": "::before",
            "nodeType": 1,
            "nodeValue": "",
        }
        paragraph = {
            "backendNodeId": 6,
            "nodeId": 106,
            "nodeName": "P",
            "nodeType": 1,
            "nodeValue": "",
            "children": [text],
            "pseudoElements": [pseudo],
        }
        body = {
            "backendNodeId": 5,
            "nodeId": 105,
            "nodeName": "BODY",
            "nodeType": 1,
            "nodeValue": "",
            "children": [paragraph],
        }
        meta = {
            "backendNodeId": 4,
            "nodeId": 104,
            "nodeName": "META",
            "nodeType": 1,
            "nodeValue": "",
            "attributes": ["name", "color-scheme"],
        }
        html = {
            "backendNodeId": 3,
            "nodeId": 103,
            "nodeName": "HTML",
            "nodeType": 1,
            "nodeValue": "",
            "children": [
                {
                    "backendNodeId": 9,
                    "nodeId": 109,
                    "nodeName": "HEAD",
                    "nodeType": 1,
                    "nodeValue": "",
                    "children": [meta],
                },
                body,
            ],
        }
        empty_html = {
            "backendNodeId": 2,
            "nodeId": 102,
            "nodeName": "HTML",
            "nodeType": 1,
            "nodeValue": "",
        }
        document = {
            "backendNodeId": 1,
            "nodeId": 101,
            "nodeName": "#document",
            "nodeType": 9,
            "nodeValue": "",
            "children": [empty_html, html],
        }
        layout_nodes = {
            5: {"tag_name": "body", "styles": {}},
            6: {"tag_name": "p", "styles": {}},
            7: {"tag_name": "#text", "styles": {}},
            8: {"tag_name": "::before", "styles": {}},
        }

        approved, html_id, _body_id, _owners, _metas = approve_elements.fn(
            set(),
            layout_nodes,
            FakePageBuilder(document),
        )
        elements = build_element_tree.fn(approved, layout_nodes, html_id)

        self.assertNotIn(2, elements)
        self.assertEqual(3, html_id)
        self.assertEqual(["#text", "::before"], [child.tag_name for child in elements[6].children])
        self.assertIs(elements[6], elements[7].parent)
        self.assertIs(elements[6], elements[8].parent)


if __name__ == "__main__":
    unittest.main()
