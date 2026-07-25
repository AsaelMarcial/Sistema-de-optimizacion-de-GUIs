from pathlib import Path
import unittest

from engine.domain.models.element import Element, Property
from engine.pipeline.pipeline import _change_history_groups
from engine.pipeline.stages.transform_design import _transform_property


ROOT = Path(__file__).resolve().parents[1]


def read_workspace_file(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class UIAccessibilityTemplatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.header = read_workspace_file("app/templates/header.html")
        self.index = read_workspace_file("app/templates/index.html")
        self.results = read_workspace_file("app/templates/results.html")
        self.css = read_workspace_file("app/static/css/results.css")

    def test_header_exposes_skip_link_and_spanish_accessible_labels(self) -> None:
        self.assertIn('class="skip-link"', self.header)
        self.assertIn('href="#main-content"', self.header)
        self.assertIn("Saltar al contenido principal", self.header)
        self.assertIn('aria-label="Inicio de GLOW"', self.header)
        self.assertIn('aria-label="Navegación principal"', self.header)
        self.assertIn('width="296"', self.header)
        self.assertIn('height="68"', self.header)
        self.assertIn("results and results.view.change_history_groups", self.header)

    def test_main_content_targets_exist_for_skip_link(self) -> None:
        self.assertIn('<main id="main-content" class="landing-page">', self.index)
        self.assertIn('id="main-content"', self.results)

    def test_upload_control_uses_native_file_input_label_path(self) -> None:
        self.assertIn("<label", self.index)
        self.assertIn('class="upload-box card card--soft"', self.index)
        self.assertIn('for="file-input"', self.index)
        self.assertNotIn('role="button"', self.index)
        self.assertNotIn('tabindex="0"', self.index)
        self.assertNotIn("onchange=", self.index)
        self.assertIn('aria-describedby="upload-helper upload-hint"', self.index)
        self.assertNotIn("onclick=", self.index)

    def test_landing_steps_have_a_programmatic_heading(self) -> None:
        self.assertIn('<h2 id="how-it-works-title" class="sr-only">Cómo funciona</h2>', self.index)
        self.assertIn('aria-labelledby="how-it-works-title"', self.index)

    def test_head_metadata_and_font_hints_are_present(self) -> None:
        for template in (self.index, self.results):
            self.assertIn('<meta name="color-scheme" content="dark" />', template)
            self.assertIn('<meta name="theme-color" content="#050505" />', template)
            self.assertIn('rel="preconnect" href="https://fonts.googleapis.com"', template)
            self.assertIn('rel="preconnect" href="https://fonts.gstatic.com" crossorigin', template)
        self.assertIn("Material+Icons&display=swap", self.results)

    def test_results_number_inputs_include_accessible_mobile_attributes(self) -> None:
        self.assertNotIn("onsubmit=", self.results)
        self.assertNotIn("onclick=", self.results)
        self.assertIn('id="impact-controls"', self.results)
        self.assertIn('id="update-impact-button" type="submit"', self.results)
        self.assertIn('name="user_count"', self.results)
        self.assertIn('name="usage_hours"', self.results)
        self.assertEqual(self.results.count('inputmode="numeric"'), 2)
        self.assertEqual(self.results.count('autocomplete="off"'), 2)
        self.assertEqual(self.results.count('step="1"'), 2)

    def test_results_previews_render_at_natural_image_height(self) -> None:
        self.assertNotIn("preview-window__viewport", self.results)
        self.assertNotIn(".preview-window__viewport", self.css)
        self.assertEqual(self.results.count('class="preview-window__image"'), 2)
        self.assertIn("height: auto;", self.css)
        self.assertNotIn("height: clamp(280px, 32.5rem, 520px);", self.css)

    def test_change_history_uses_element_accordions(self) -> None:
        self.assertIn('<details class="card card--soft change-group">', self.results)
        self.assertIn('class="change-group__toggle"', self.results)
        self.assertIn("{{ group.title | upper }}", self.results)
        self.assertIn("{{ group.change_count }} {{ 'cambio' if group.change_count == 1 else 'cambios' }}", self.results)
        self.assertIn("class=\"change-swatch\"", self.results)
        self.assertIn("{{ change.before_label }}", self.results)
        self.assertIn(".change-group__head::-webkit-details-marker", self.css)
        self.assertIn("grid-template-columns: 1fr;", self.css)

    def test_palette_rows_fit_available_space_and_show_copy_feedback(self) -> None:
        self.assertNotIn("palette-meta__count", self.results)
        self.assertNotIn("swatch__tone", self.results)
        self.assertNotIn("swatch__icon", self.results)
        self.assertNotIn(".palette-meta__count", self.css)
        self.assertNotIn(".swatch__tone", self.css)
        self.assertIn("grid-template-columns: repeat(var(--swatch-count), minmax(0, 1fr));", self.css)
        self.assertIn(".swatch::after", self.css)
        self.assertIn('content: "Copiar";', self.css)
        self.assertIn(".swatch.copied::after", self.css)
        self.assertIn('content: "Copiado";', self.css)

    def test_contrast_card_uses_compact_card_layout(self) -> None:
        self.assertIn(".contrast-card", self.css)
        self.assertIn("align-self: start;", self.css)
        self.assertIn("contrast_group_count = contrast_groups.keys | length", self.results)
        self.assertIn("'grupo' if contrast_group_count == 1 else 'grupos'", self.results)
        self.assertIn('class="contrast-item__count"', self.results)
        self.assertIn(".contrast-item__count", self.css)
        self.assertNotIn("padding: 0;\n  border: 0;\n  background: none;", self.css)

    def test_css_accessibility_contracts(self) -> None:
        self.assertIn("color-scheme: only dark;", self.css)
        self.assertIn("--text-caption: rgba(216, 225, 234, 0.66);", self.css)
        self.assertIn("@media (prefers-reduced-motion: no-preference)", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn("scroll-behavior: auto;", self.css)
        self.assertIn(".button:focus-visible", self.css)
        self.assertIn(".button--primary:hover", self.css)
        self.assertIn(".button--primary:active", self.css)
        self.assertIn(".field input:focus-visible", self.css)
        self.assertIn(".brand-logo:focus-visible", self.css)
        self.assertIn(".details summary:focus-visible", self.css)
        self.assertIn(".landing-page .upload-box:focus-within", self.css)
        self.assertIn(".nav .button--primary", self.css)
        self.assertNotIn(".nav .primary-btn", self.css)
        self.assertNotIn("object-fit: cover;", self.css)
        self.assertNotIn("letter-spacing: -", self.css)
        self.assertNotRegex(self.css, r"font-size:\s*clamp\([^;]*vw")

    def test_property_has_changed_uses_after_value(self) -> None:
        unchanged = Property(
            name="color",
            before_value="rgb(255, 255, 255)",
        )
        same_value = Property(
            name="color",
            before_value="rgb(255, 255, 255)",
            after_value="rgb(255, 255, 255)",
        )
        changed = Property(
            name="background-color",
            before_value="rgb(255, 255, 255)",
            after_value="rgb(0, 0, 0)",
        )

        self.assertFalse(unchanged.has_changed)
        self.assertFalse(same_value.has_changed)
        self.assertTrue(changed.has_changed)

    def test_change_history_groups_are_grouped_by_element_instance(self) -> None:
        root = Element(
            backend_node_id=10,
            node_id=100,
            tag_name="body",
            node_type=1,
            properties=[
                Property("background-color", "white", "black"),
                Property("color", "black", "white"),
                Property("border-color", "red"),
            ],
        )
        second_body = Element(
            backend_node_id=20,
            node_id=200,
            tag_name="body",
            node_type=1,
            properties=[
                Property("background-color", "red", "blue"),
            ],
        )
        root.add_child(second_body)

        groups = _change_history_groups(root)

        self.assertEqual(2, len(groups))
        self.assertEqual("Body", groups[0]["title"])
        self.assertEqual(10, groups[0]["backend_node_id"])
        self.assertEqual(2, groups[0]["change_count"])
        self.assertEqual(
            ("background-color", "color"),
            tuple(change["property_name"] for change in groups[0]["changes"]),
        )
        self.assertEqual("white", groups[0]["changes"][0]["before_value"])
        self.assertEqual("black", groups[0]["changes"][0]["after_value"])
        self.assertEqual("white", groups[0]["changes"][0]["before_css"])
        self.assertEqual("black", groups[0]["changes"][0]["after_css"])
        self.assertEqual("Body", groups[1]["title"])
        self.assertEqual(20, groups[1]["backend_node_id"])

    def test_transform_property_applies_and_records_element_change(self) -> None:
        class FakePageBuilder:
            def __init__(self) -> None:
                self.calls = []

            def set_effective_value(
                self,
                node_id: int,
                property_name: str,
                value: str,
            ) -> str:
                self.calls.append((node_id, property_name, value))
                return value

        page_builder = FakePageBuilder()
        element = Element(
            backend_node_id=20,
            node_id=200,
            tag_name="button",
            node_type=1,
            properties=[
                Property(
                    name="background-color",
                    before_value="rgb(255, 255, 255)",
                ),
                Property(
                    name="color",
                    before_value="rgb(0, 0, 0)",
                ),
            ],
        )

        _transform_property(
            page_builder,
            element,
            "background-color",
            "rgb(0, 0, 0)",
        )
        _transform_property(
            page_builder,
            element,
            "color",
            "rgb(0, 0, 0)",
        )
        _transform_property(
            page_builder,
            element,
            "border-color",
            "rgb(20, 20, 20)",
        )

        self.assertEqual(
            [
                (200, "background-color", "rgb(0, 0, 0)"),
                (200, "border-color", "rgb(20, 20, 20)"),
            ],
            page_builder.calls,
        )
        self.assertEqual(
            "rgb(0, 0, 0)",
            element.property("background-color").after_value,
        )
        self.assertIsNone(element.property("color").after_value)
        self.assertEqual("", element.property("border-color").before_value)
        self.assertEqual(
            "rgb(20, 20, 20)",
            element.property("border-color").after_value,
        )


if __name__ == "__main__":
    unittest.main()
