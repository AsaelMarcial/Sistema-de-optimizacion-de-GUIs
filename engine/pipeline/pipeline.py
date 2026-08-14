from __future__ import annotations

from typing import Any

from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.debug_trace import DebugTrace
from engine.pipeline.stage_contract import PipelineContractError, StageContract, validate_produces, validate_requires
from engine.pipeline.stages.build_results import CONTRACT as BUILD_RESULTS_CONTRACT
from engine.pipeline.stages.build_results import run_stage as run_build_results_stage
from engine.pipeline.stages.capture_original_state import CONTRACT as CAPTURE_ORIGINAL_STATE_CONTRACT
from engine.pipeline.stages.capture_original_state import run_stage as run_capture_original_state_stage
from engine.pipeline.stages.assess_enviromental_impact import CONTRACT as ASSESS_ENVIROMENTAL_IMPACT_CONTRACT
from engine.pipeline.stages.assess_enviromental_impact import run_stage as run_assess_enviromental_impact_stage
from engine.pipeline.stages.close_page_builder import CONTRACT as CLOSE_PAGE_BUILDER_CONTRACT
from engine.pipeline.stages.close_page_builder import run_stage as run_close_page_builder_stage
from engine.pipeline.stages.data_processor import CONTRACT as DATA_PROCESSOR_CONTRACT
from engine.pipeline.stages.data_processor import run_stage as run_data_processor_stage
from engine.pipeline.stages.prepare_project_session import CONTRACT as PREPARE_PROJECT_SESSION_CONTRACT
from engine.pipeline.stages.prepare_project_session import run_stage as run_prepare_project_session_stage
from engine.pipeline.stages.start_page_builder import CONTRACT as START_PAGE_BUILDER_CONTRACT
from engine.pipeline.stages.start_page_builder import run_stage as run_start_page_builder_stage
from engine.pipeline.stages.transform_design import CONTRACT as TRANSFORM_DESIGN_CONTRACT
from engine.pipeline.stages.transform_design import run_stage as run_transform_design_stage
_STAGES: tuple[tuple[StageContract, Any], ...] = (
    (START_PAGE_BUILDER_CONTRACT, run_start_page_builder_stage),
    (CAPTURE_ORIGINAL_STATE_CONTRACT, run_capture_original_state_stage),
    (DATA_PROCESSOR_CONTRACT, run_data_processor_stage),
    (TRANSFORM_DESIGN_CONTRACT, run_transform_design_stage),
    (ASSESS_ENVIROMENTAL_IMPACT_CONTRACT, run_assess_enviromental_impact_stage),
    (BUILD_RESULTS_CONTRACT, run_build_results_stage),
    (CLOSE_PAGE_BUILDER_CONTRACT, run_close_page_builder_stage),
)


def _close_page_builder(context: PipelineContext) -> None:
    page_builder = context.get(K.PAGE_BUILDER)
    close = getattr(page_builder, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass
    context.delete(K.PAGE_BUILDER)


def run_pipeline(file) -> tuple[PipelineContext | None, str | None]:
    context = PipelineContext(trace=DebugTrace(enabled=True))
    try:
        try:
            context.trace.add_stage_event(PREPARE_PROJECT_SESSION_CONTRACT.name, "validate_requires")
            validate_requires(context, PREPARE_PROJECT_SESSION_CONTRACT)
            context = run_prepare_project_session_stage(context, file)
            if not context.error:
                context.trace.add_stage_event(PREPARE_PROJECT_SESSION_CONTRACT.name, "validate_produces")
                validate_produces(context, PREPARE_PROJECT_SESSION_CONTRACT)
        except PipelineContractError as exc:
            context.set_error(str(exc))
            context.trace.add_stage_event(
                PREPARE_PROJECT_SESSION_CONTRACT.name,
                "error",
                {"message": context.error},
            )
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            context.set_error(str(exc))
            context.trace.add_stage_event(
                PREPARE_PROJECT_SESSION_CONTRACT.name,
                "error",
                {"message": context.error},
            )

        for contract, stage_runner in _STAGES:
            if context.error:
                break
            try:
                context.trace.add_stage_event(contract.name, "validate_requires")
                validate_requires(context, contract)
                context = stage_runner(context)
                if context.error:
                    context.trace.add_stage_event(
                        contract.name,
                        "error",
                        {"message": context.error},
                    )
                    break
                context.trace.add_stage_event(contract.name, "validate_produces")
                validate_produces(context, contract)
            except PipelineContractError as exc:
                context.set_error(str(exc))
                context.trace.add_stage_event(
                    contract.name,
                    "error",
                    {"message": context.error},
                )
                break
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                context.set_error(str(exc))
                context.trace.add_stage_event(
                    contract.name,
                    "error",
                    {"message": context.error},
                )
                break
    finally:
        if context.has(K.PAGE_BUILDER):
            _close_page_builder(context)
    return (None if context.error else context), context.error
