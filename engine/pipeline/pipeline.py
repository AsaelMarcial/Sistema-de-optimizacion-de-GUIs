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
        prepare_project_session_done = prepare_project_session(context, file, return_state=True)
        if prepare_project_session_done.is_failed():
            return prepare_project_session_done

        start_page_builder_done = start_page_builder(context, return_state=True)
        if start_page_builder_done.is_failed():
            return start_page_builder_done

        capture_original_state_done = capture_original_state(context, return_state=True)
        if capture_original_state_done.is_failed():
            return capture_original_state_done

        data_processor_done = data_processor(context, return_state=True)
        if data_processor_done.is_failed():
            return data_processor_done

        transform_design_done = transform_design(context, return_state=True)
        if transform_design_done.is_failed():
            return transform_design_done

        assess_enviromental_impact_done = assess_enviromental_impact(context, return_state=True)
        if assess_enviromental_impact_done.is_failed():
            return assess_enviromental_impact_done

        build_results_done = build_results(context, return_state=True)
        if build_results_done.is_failed():
            return build_results_done

        return context
