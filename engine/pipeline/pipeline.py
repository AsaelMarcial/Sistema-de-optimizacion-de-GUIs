from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.browser.server import StaticServer
from engine.pipeline.context import PipelineContext
from engine.pipeline.glow_runtime import glow_flow
from engine.pipeline.stages.assess_enviromental_impact import (
    assess_enviromental_impact,
)
from engine.pipeline.stages.build_results import build_results
from engine.pipeline.stages.capture_original_state import (
    capture_original_state,
)
from engine.pipeline.stages.data_processor import data_processor
from engine.pipeline.stages.prepare_project_session import (
    prepare_project_session,
)
from engine.pipeline.stages.static_evaluation import (
    static_evaluation,
)
from engine.pipeline.stages.transform_design import transform_design


@glow_flow
def pipeline(file):
    with PipelineContext() as context:
        prepare_project_session(
            context.session,
            context.asset_records,
            file,
        )
        static_evaluation(
            context.session,
            context.style,
            context.asset_records,
        )

        before_root = context.session.get_area_root("before")
        html_path = context.session.get_by_type(".html")[0]
        with StaticServer(before_root) as server, PageBuilder(
            server,
            context.style,
            context.asset_records,
            html_path=html_path,
        ) as page_builder:
            loaded_assets = tuple(
                asset
                for asset in context.asset_records
                if asset.has_network_information and asset.load_status
            )
            failed_assets = tuple(
                asset
                for asset in context.asset_records
                if asset.has_network_information and not asset.load_status
            )

            print({
                "page_builder.runtime_ready": {
                    "html_path": str(page_builder.html_path),
                    "base_path": str(page_builder.base_path),
                    "document_root_node_id": page_builder.document_root.get("nodeId"),
                    "stylesheets": len(context.style.stylesheets),
                    "network_loaded_assets": len(loaded_assets),
                    "network_failed_assets": len(failed_assets),
                }
            })
            capture_original_state(
                context.session,
                page_builder,
                context.color_scheme,
                context.asset_records,
                context.dom_tree,
            )
            data_processor(
                context.session,
                page_builder,
                context.dom_tree,
                context.color_scheme,
                context.summary,
            )
            transform_design(
                context.session,
                page_builder,
                context.dom_tree,
                context.color_scheme,
                context.token_inventory,
                context.asset_records,
            )
            assess_enviromental_impact(
                context.session,
                context.summary,
            )
            build_results(
                context.session,
                page_builder,
                context.color_scheme,
            )

        return context
