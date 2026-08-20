from __future__ import annotations

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
from engine.pipeline.stages.start_page_builder import (
    start_page_builder,
)
from engine.pipeline.stages.transform_design import transform_design


@glow_flow
def pipeline(file):
    with PipelineContext() as context:
        prepare_project_session(context, file)
        start_page_builder(context)
        capture_original_state(context)
        data_processor(context)
        transform_design(context)
        assess_enviromental_impact(context)
        build_results(context)

        return context
