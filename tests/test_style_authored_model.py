from __future__ import annotations

import unittest

from engine.domain.models.style import (
    DeclarationSyntax,
    Selector,
    StyleCatalog,
    StyleSourceKind,
)


class StyleAuthoredModelTests(unittest.TestCase):
    def _add_rule(
        self,
        catalog: StyleCatalog,
        *,
        source_kind: StyleSourceKind,
        selectors=(),
        stylesheet_id: str | None = None,
        source_url: str | None = None,
        owner_element_id: str | None = None,
    ):
        source = catalog.add_source(
            kind=source_kind,
            stylesheet_id=stylesheet_id,
            href=source_url,
            owner_node_id=owner_element_id,
        )
        return source.add_rule(selectors=selectors)

    def test_catalog_partitions_inline_external_and_embedded_rules(self) -> None:
        catalog = StyleCatalog()

        inline_rule = self._add_rule(
            catalog,
            source_kind=StyleSourceKind.INLINE,
            selectors=(":scope",),
            owner_element_id="element-1",
        )
        embedded_rule = self._add_rule(
            catalog,
            source_kind=StyleSourceKind.EMBEDDED,
            selectors=(".card",),
        )
        external_rule = self._add_rule(
            catalog,
            source_kind=StyleSourceKind.EXTERNAL,
            selectors=("body",),
            stylesheet_id="sheet-1",
            source_url="/static/site.css",
        )

        self.assertEqual((inline_rule.rule_id,), tuple(rule.rule_id for rule in catalog.inline_rules))
        self.assertEqual((embedded_rule.rule_id,), tuple(rule.rule_id for rule in catalog.rules_for_source_kind(StyleSourceKind.EMBEDDED)))
        self.assertEqual((external_rule.rule_id,), tuple(rule.rule_id for rule in catalog.rules_for_source_kind(StyleSourceKind.EXTERNAL)))
        self.assertEqual("sheet-1", catalog.external_sources[0].stylesheet_id)

    def test_catalog_creates_rules_in_stable_order(self) -> None:
        catalog = StyleCatalog()

        first = self._add_rule(
            catalog,
            source_kind=StyleSourceKind.EXTERNAL,
            selectors=("body",),
        )
        second = self._add_rule(
            catalog,
            source_kind=StyleSourceKind.EMBEDDED,
            selectors=(".card",),
        )

        self.assertEqual((first.rule_id, second.rule_id), tuple(rule.rule_id for rule in catalog.rules))

    def test_rule_allows_multiple_declarations_with_same_name(self) -> None:
        catalog = StyleCatalog()
        rule = self._add_rule(
            catalog,
            source_kind=StyleSourceKind.EXTERNAL,
            selectors=(".card",),
        )

        first = rule.add_declaration(name="color", value_text="red")
        second = rule.add_declaration(name="color", value_text="blue")

        self.assertNotEqual(first.declaration_id, second.declaration_id)
        self.assertEqual(("red", "blue"), tuple(item.value_text for item in rule.get_declarations("color")))

    def test_shorthand_covers_nested_longhands(self) -> None:
        catalog = StyleCatalog()
        rule = self._add_rule(
            catalog,
            source_kind=StyleSourceKind.EXTERNAL,
            selectors=(".card",),
        )

        border = rule.add_declaration(name="border", value_text="1px solid red")
        margin = rule.add_declaration(name="margin", value_text="1rem")

        self.assertTrue(border.covers_property("border-top-color"))
        self.assertTrue(border.covers_property("border-left-style"))
        self.assertTrue(border.covers_property("border-right-width"))
        self.assertTrue(margin.covers_property("margin-bottom"))

    def test_rule_used_is_derived_from_selector_usage(self) -> None:
        catalog = StyleCatalog()
        rule = self._add_rule(
            catalog,
            source_kind=StyleSourceKind.EXTERNAL,
            selectors=("body", ".page"),
        )

        self.assertFalse(rule.used)
        rule.selectors[1].mark_used()
        self.assertTrue(rule.used)
        self.assertFalse(rule.selectors[0].used)
        self.assertTrue(rule.selectors[1].used)

    def test_split_grouped_rule_preserves_declarations(self) -> None:
        catalog = StyleCatalog()
        rule = self._add_rule(
            catalog,
            source_kind=StyleSourceKind.EXTERNAL,
            selectors=("body", ".page"),
        )
        rule.add_declaration(name="color", value_text="red")
        rule.add_declaration(
            name="margin",
            value_text="1rem",
            syntax=DeclarationSyntax.SHORTHAND,
            covered_longhands=("margin-top", "margin-right", "margin-bottom", "margin-left"),
        )

        split_rule = catalog.split_grouped_rule(rule.rule_id, selector_ids=(rule.selectors[1].selector_id,))

        self.assertEqual(("body",), tuple(selector.text for selector in rule.selectors))
        self.assertEqual((".page",), tuple(selector.text for selector in split_rule.selectors))
        self.assertEqual(2, len(rule.declarations))
        self.assertEqual(2, len(split_rule.declarations))
        self.assertNotEqual(rule.declarations[0].declaration_id, split_rule.declarations[0].declaration_id)

    def test_root_custom_property_declarations_are_stored_as_regular_declarations(self) -> None:
        catalog = StyleCatalog()
        root_rule = self._add_rule(
            catalog,
            source_kind=StyleSourceKind.EMBEDDED,
            selectors=(":root",),
        )
        primary = root_rule.add_declaration(name="--primary", value_text="oklch(60% 0.18 280)")
        alias = root_rule.add_declaration(
            name="--primary-strong",
            value_text="var(--primary)",
        )

        root_declarations = catalog.root_custom_property_declarations()

        self.assertEqual((primary.declaration_id, alias.declaration_id), tuple(item.declaration_id for item in root_declarations))
        self.assertEqual("var(--primary)", alias.value_text)
        self.assertIs(alias, catalog.get_declaration(rule_id=root_rule.rule_id, name="--primary-strong"))

    def test_catalog_get_declaration_resolves_through_rules(self) -> None:
        catalog = StyleCatalog()
        source = catalog.add_source(
            kind=StyleSourceKind.INLINE,
            owner_node_id="element-1",
        )
        rule = source.add_rule(selectors=(Selector(selector_id="inline-1", text=":scope", order_in_group=0),))
        declaration = rule.add_declaration(name="color", value_text="red")

        self.assertIs(declaration, catalog.get_declaration(declaration.declaration_id))


if __name__ == "__main__":
    unittest.main()
