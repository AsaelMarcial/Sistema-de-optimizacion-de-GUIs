from __future__ import annotations

from engine.adapters.source_code_handler.local_asset_rewriter import (
    rewrite_local_asset_references,
)
from engine.domain.models.asset_records import AssetRecords
from engine.domain.models.session import Session
from engine.domain.models.style import Styles
from engine.pipeline.glow_runtime import glow_flow


@glow_flow
def static_evaluation(
    session: Session,
    style: Styles,
    asset_records: AssetRecords,
):
    html_files = tuple(session.get_by_type(".html"))
    before_root = session.get_area_root("before")

    html_file = html_files[0]
    rewritten_values = rewrite_local_asset_references(
        html_file,
        session,
        asset_records,
    )
    if rewritten_values:
        print({
            "html.asset_paths_rewritten": {
                "rewrite_count": len(rewritten_values),
                "html_path": str(html_file),
            }
        })

    style.clear()

    print({
        "static_evaluation.complete": {
            "html_path": str(html_file),
            "before_root": str(before_root),
            "asset_count": len(asset_records),
        }
    })
