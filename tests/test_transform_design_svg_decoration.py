import shutil
import unittest
from pathlib import Path

from flask import Flask, g

from engine.domain.models.project_context import ProjectContext, Resource
from engine.domain.models.element import DomTree, Element, Property
from engine.domain.models.token import TokenInventory
from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.transform_design import (
    _process_loaded_svg_files,
    _surface_depth,
)


class FakePageBuilder:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.attribute_values: dict[tuple[int, str], str] = {}
        self.property_values: dict[tuple[int, str], str] = {}

    def set_attribute_value(
        self,
        node_id: int,
        attribute_name: str,
        value: str,
    ) -> str:
        self.attribute_values[(node_id, attribute_name)] = value
        return value

    def set_effective_value(
        self,
        backend_node_id: int,
        node_id: int,
        property_name: str,
        value: str,
        tag_name: str = "",
    ) -> None:
        self.property_values[(node_id, property_name)] = value

    def current_property_value(
        self,
        node_id: int,
        property_name: str,
    ) -> str:
        return self.property_values[(node_id, property_name)]


class TransformDesignSvgDecorationTest(unittest.TestCase):
    def test_surface_depth_does_not_depend_on_body_box_model(self) -> None:
        body = Element(
            backend_node_id=1,
            node_id=10,
            tag_name="body",
            category="main-surface",
            node_type=1,
        )
        parent = Element(
            backend_node_id=2,
            node_id=20,
            tag_name="section",
            category="container",
            node_type=1,
            box_model={"content": []},
            width=100,
            height=100,
        )
        child = Element(
            backend_node_id=3,
            node_id=30,
            tag_name="article",
            category="container",
            node_type=1,
            box_model={"content": []},
            width=50,
            height=50,
        )

        body.add_child(parent)
        parent.add_child(child)

        self.assertEqual(1, _surface_depth(parent))
        self.assertEqual(2, _surface_depth(child))

    def test_property_tokens_ignore_attribute_assets_and_inherited_calculated_values(self) -> None:
        root = Element(
            backend_node_id=1,
            node_id=10,
            tag_name="body",
            category="main-surface",
            node_type=1,
            properties=[
                Property(
                    name="srcset",
                    before_value="wide.png 1x",
                    resource=Resource(url="wide.png"),
                    type="attribute",
                    is_defined=True,
                ),
                Property(
                    name="color",
                    before_value="rgb(0, 0, 0)",
                    calculated_value="rgb(255, 255, 255)",
                    type="inherited",
                ),
                Property(
                    name="background-color",
                    before_value="rgb(255, 255, 255)",
                    calculated_value="rgb(0, 0, 0)",
                    type="matched",
                    is_defined=True,
                ),
            ],
        )

        tokens = TokenInventory().generate_property_tokens(root)
        token_refs = {
            ref
            for token in tokens.values()
            for ref in token.element_ids
        }

        self.assertEqual({(10, "background-color")}, token_refs)

    def test_loaded_svg_updates_every_element_usage(self) -> None:
        app_context = Flask(__name__).app_context()
        app_context.push()
        PipelineContext()
        session_dir = g.session_dir
        shutil.rmtree(session_dir, ignore_errors=True)
        before_root = g.before_root
        project_dir = before_root / "site"
        project_dir.mkdir(parents=True, exist_ok=True)
        g.after_root.mkdir(parents=True, exist_ok=True)
        g.artifacts_root.mkdir(parents=True, exist_ok=True)
        (project_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        (project_dir / "assets").mkdir(parents=True, exist_ok=True)
        (project_dir / "assets" / "icon.svg").write_bytes(
            b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        )
        project_context = ProjectContext(
            [
                {"file_name": Path("site/index.html"), "mime_type": "text/html"},
                {
                    "file_name": Path("site/assets/icon.svg"),
                    "mime_type": "image/svg+xml",
                },
            ],
        )
        try:
            project_context.page_url = "http://127.0.0.1:8000/site/index.html"
            svg_file = project_context.project_file("site/assets/icon.svg")
            self.assertIsNotNone(svg_file)
            svg_resource = project_context.add_resource(
                "http://127.0.0.1:8000/site/assets/icon.svg",
                resource_type="image",
                load_status=True,
            )

            body = Element(
                backend_node_id=1,
                node_id=10,
                tag_name="body",
                category="main-surface",
                node_type=1,
            )
            first = Element(
                backend_node_id=2,
                node_id=20,
                tag_name="img",
                category="media",
                node_type=1,
                properties=[
                    Property(
                        name="src",
                        before_value="assets/icon.svg",
                        resource=svg_resource,
                        type="attribute",
                        is_defined=True,
                    ),
                ],
            )
            second = Element(
                backend_node_id=3,
                node_id=30,
                tag_name="div",
                category="container",
                node_type=1,
                properties=[
                    Property(
                        name="background-image",
                        before_value='url("assets/icon.svg")',
                        resource=svg_resource,
                        type="matched",
                        is_defined=True,
                    ),
                ],
            )
            body.add_child(first)
            body.add_child(second)
            dom_tree = DomTree(
                html=body,
                body=body,
                elements={
                    body.backend_node_id: body,
                    first.backend_node_id: first,
                    second.backend_node_id: second,
                },
            )
            svg_file.add_usage(first.backend_node_id)
            svg_file.add_usage(second.backend_node_id)

            page_builder = FakePageBuilder(project_dir)

            _process_loaded_svg_files(
                project_context=project_context,
                page_builder=page_builder,
                dom_tree=dom_tree,
                original_backgrounds={},
                color_scheme=None,
            )

            versions = svg_file.versions
            self.assertEqual(1, len(versions))
            self.assertTrue((project_dir / "assets" / "icon-glow.svg").is_file())
            self.assertEqual(
                "assets/icon-glow.svg",
                page_builder.attribute_values[(20, "src")],
            )
            self.assertIn(
                "url(assets/icon-glow.svg)",
                second.properties[0].after_value or "",
            )
            self.assertIs(first.properties[0].resource.project_file, versions[0])
            self.assertIs(second.properties[0].resource.project_file, versions[0])
        finally:
            app_context.pop()
            shutil.rmtree(session_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
