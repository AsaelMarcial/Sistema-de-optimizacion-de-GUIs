from __future__ import annotations

from flask import g

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
        g.upload = file
        prepare_project_session()
        static_evaluation()

        with (
            StaticServer(g.before_root) as server,
            PageBuilder(
                server,
            ) as page_builder,
        ):
            g.page_builder = page_builder
            print(
                {
                    "page_builder.runtime_ready": {
                        "html_path": str(page_builder.html_path),
                        "base_path": str(page_builder.base_path),
                        "document_root_node_id": page_builder.document_root.get(
                            "nodeId"
                        ),
                        "stylesheets": len(g.style.stylesheets),
                        "network_loaded_assets": sum(
                            1
                            for resource in g.project_context.resources.values()
                            if resource.load_status is True
                        ),
                        "network_failed_assets": len(
                            g.project_context.failed_resources()
                        ),
                    }
                }
            )
            capture_original_state()
            data_processor()
            transform_design()
            assess_enviromental_impact()
            build_results()

        return context
