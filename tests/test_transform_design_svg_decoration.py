import shutil
import unittest
from pathlib import Path

from engine.adapters.source_code_handler.local_asset_rewriter import (
    extract_reference_candidates,
)
from engine.domain.models.element import Element, Property
from engine.domain.models.session import Session, Source
from engine.domain.models.token import TokenInventory
from engine.pipeline.stages.transform_design import (
    _process_external_svg_decoration,
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
    def test_extract_reference_candidates_handles_attributes_and_css_urls(self) -> None:
        self.assertEqual(
            ["icons/large.svg", "icons/small.svg"],
            sorted(
                extract_reference_candidates(
                    "icons/small.svg 1x, icons/large.svg 2x",
                    "srcset",
                )
            ),
        )
        self.assertEqual([], extract_reference_candidates("#icon", "href"))
        self.assertEqual(
            ["icons/icon.svg"],
            extract_reference_candidates(
                'linear-gradient(red, blue), url("icons/icon.svg")'
            ),
        )

    def test_property_tokens_ignore_attribute_image_sources_and_inherited_calculated_values(self) -> None:
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
                    image_source=Source(Path("wide.png"), "local"),
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

    def test_external_svg_decoration_uses_image_source_and_source_versions(self) -> None:
        session = Session()
        try:
            before_root = session.get_area_root("before")
            project_dir = before_root / "site"
            svg_path = project_dir / "assets" / "icon.svg"
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
                encoding="utf-8",
            )
            session.file_types[svg_path.resolve()] = ".svg"
            source = session.register_source("missing/icon.svg", load_status="loaded")

            element = Element(
                backend_node_id=10,
                node_id=20,
                tag_name="div",
                category="decoration",
                node_type=1,
                properties=[
                    Property(
                        name="data-icon",
                        before_value="missing/icon.svg",
                        image_source=source,
                        type="attribute",
                        is_defined=True,
                    ),
                    Property(
                        name="background-image",
                        before_value='linear-gradient(red, blue), url("missing/icon.svg")',
                        image_source=source,
                        type="matched",
                        is_defined=True,
                    )
                ],
            )
            page_builder = FakePageBuilder(project_dir)

            _process_external_svg_decoration(
                session=session,
                page_builder=page_builder,
                element=element,
                original_ancestor_background_colors=None,
                actual_ancestor_background_colors=None,
                color_scheme=None,
            )

            glow_path = project_dir / "assets" / "icon-glow.svg"
            self.assertTrue(glow_path.is_file())
            self.assertEqual(1, len(source.versions))
            self.assertEqual(
                "assets/icon-glow.svg",
                element.attributes[0].current_value,
            )
            self.assertEqual(
                "assets/icon-glow.svg",
                page_builder.attribute_values[(20, "data-icon")],
            )
            background_image = next(
                property_model
                for property_model in element.properties
                if property_model.name == "background-image"
            )
            self.assertIn(
                "url(assets/icon-glow.svg)",
                background_image.after_value or "",
            )
            self.assertIn(
                "linear-gradient(red, blue)",
                background_image.after_value or "",
            )
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_external_svg_decoration_reuses_existing_source_version(self) -> None:
        session = Session()
        try:
            before_root = session.get_area_root("before")
            project_dir = before_root / "site"
            svg_path = project_dir / "assets" / "icon.svg"
            glow_path = project_dir / "assets" / "icon-glow.svg"
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text("<svg></svg>", encoding="utf-8")
            glow_path.write_text("<svg></svg>", encoding="utf-8")
            session.file_types[svg_path.resolve()] = ".svg"

            source = session.register_source("missing/icon.svg", load_status="loaded")
            version_source = session.register_source(glow_path)
            source.add_version(version_source)

            element = Element(
                backend_node_id=10,
                node_id=20,
                tag_name="img",
                category="decoration",
                node_type=1,
                properties=[
                    Property(
                        name="src",
                        before_value="missing/icon.svg",
                        image_source=source,
                        type="attribute",
                        is_defined=True,
                    ),
                ],
            )
            page_builder = FakePageBuilder(project_dir)

            _process_external_svg_decoration(
                session=session,
                page_builder=page_builder,
                element=element,
                original_ancestor_background_colors=None,
                actual_ancestor_background_colors=None,
                color_scheme=None,
            )

            self.assertEqual({version_source}, source.versions)
            self.assertEqual(
                "assets/icon-glow.svg",
                page_builder.attribute_values[(20, "src")],
            )
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_external_svg_decoration_skips_unloaded_sources(self) -> None:
        session = Session()
        try:
            before_root = session.get_area_root("before")
            project_dir = before_root / "site"
            svg_path = project_dir / "assets" / "icon.svg"
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text("<svg></svg>", encoding="utf-8")
            session.file_types[svg_path.resolve()] = ".svg"
            source = session.register_source("missing/icon.svg")

            element = Element(
                backend_node_id=10,
                node_id=20,
                tag_name="img",
                category="decoration",
                node_type=1,
                properties=[
                    Property(
                        name="src",
                        before_value="missing/icon.svg",
                        image_source=source,
                        type="attribute",
                        is_defined=True,
                    ),
                ],
            )
            page_builder = FakePageBuilder(project_dir)

            _process_external_svg_decoration(
                session=session,
                page_builder=page_builder,
                element=element,
                original_ancestor_background_colors=None,
                actual_ancestor_background_colors=None,
                color_scheme=None,
            )

            self.assertEqual({}, page_builder.attribute_values)
            self.assertFalse(source.versions)
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)

    def test_external_svg_decoration_rewrites_srcset_attribute(self) -> None:
        session = Session()
        try:
            before_root = session.get_area_root("before")
            project_dir = before_root / "site"
            svg_path = project_dir / "assets" / "icon.svg"
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
                encoding="utf-8",
            )
            session.file_types[svg_path.resolve()] = ".svg"
            source = session.register_source("missing/icon.svg", load_status="loaded")

            element = Element(
                backend_node_id=10,
                node_id=20,
                tag_name="source",
                category="decoration",
                node_type=1,
                properties=[
                    Property(
                        name="srcset",
                        before_value="missing/icon.svg 1x, missing/icon.svg 2x",
                        image_source=source,
                        type="attribute",
                        is_defined=True,
                    ),
                ],
            )
            page_builder = FakePageBuilder(project_dir)

            _process_external_svg_decoration(
                session=session,
                page_builder=page_builder,
                element=element,
                original_ancestor_background_colors=None,
                actual_ancestor_background_colors=None,
                color_scheme=None,
            )

            expected = "assets/icon-glow.svg 1x, assets/icon-glow.svg 2x"
            self.assertEqual(expected, element.attributes[0].current_value)
            self.assertIs(next(iter(source.versions)), element.attributes[0].image_source)
            self.assertEqual(expected, page_builder.attribute_values[(20, "srcset")])
        finally:
            shutil.rmtree(session.session_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
