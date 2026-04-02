import unittest
from pathlib import Path

from engine.adapters.browser.snapshot_analyzer import extract_prototype_css_overview
from engine.adapters.browser.render_models import SnapshotOptions


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class CssOverviewTests(unittest.TestCase):
    def test_extract_prototype_css_overview_returns_colors_media_queries_and_contrast_issues(self) -> None:
        html_content = """
<!doctype html>
<html lang="en">
  <head>
    <style>
      body {
        margin: 0;
        color: rgb(17, 17, 17);
        background: rgb(255, 255, 255);
        font-family: Georgia, serif;
      }

      .hero {
        background: rgb(20, 40, 60);
        color: rgb(255, 255, 255);
        padding: 24px;
      }

      .muted {
        color: rgb(180, 180, 180);
      }

      .badge {
        background: rgba(0, 128, 255, 0.35);
        border: 2px solid rgb(0, 128, 255);
        font-weight: 700;
        width: 220px;
      }

      @media (min-width: 600px) {
        .hero {
          border-color: rgb(200, 0, 0);
        }
      }
    </style>
  </head>
  <body>
    <main class="hero">
      <h1>CSS Overview Sample</h1>
      <span class="badge" style="line-height: 28px;">Badge</span>
    </main>
    <p class="muted">This text should fail contrast.</p>
  </body>
</html>
"""
        overview = extract_prototype_css_overview(
            html_content,
            str(FIXTURES_DIR),
            options=SnapshotOptions(capture_screenshot=False),
        )

        self.assertEqual(overview["metadata"]["generator"], "css_overview_adapter")
        self.assertGreaterEqual(overview["summary"]["visible_element_count"], 4)
        self.assertEqual(overview["unsupported_sections"], [])

        text_colors = {entry["hex"] for entry in overview["colors"]["text"]}
        self.assertIn("#111111", text_colors)
        self.assertIn("#b4b4b4", text_colors)
        self.assertTrue(any(entry.get("node_ids") for entry in overview["colors"]["text"]))

        background_colors = {entry["hex"] for entry in overview["colors"]["background"]}
        self.assertIn("#ffffff", background_colors)
        self.assertIn("#14283c", background_colors)

        border_colors = {entry["hex"] for entry in overview["colors"]["border"]}
        self.assertIn("#0080ff", border_colors)

        self.assertTrue(
            any("Georgia" in entry["font_family"] for entry in overview["typography"]["font_families"])
        )
        self.assertTrue(any(entry["text"] == "(min-width: 600px)" for entry in overview["media_queries"]))
        self.assertTrue(any("p.muted" in issue["selector"] for issue in overview["contrast_issues"]))
        self.assertTrue(all(issue.get("node_id") for issue in overview["contrast_issues"]))
        self.assertGreater(overview["unused_declarations"]["count"], 0)
        self.assertTrue(
            any(
                entry["property"] == "width" and "span.badge" in entry["selector"]
                for entry in overview["unused_declarations"]["entries"]
            )
        )

        issue = next(issue for issue in overview["contrast_issues"] if "p.muted" in issue["selector"])
        self.assertLess(issue["contrast_ratio"], issue["required_ratio"])
