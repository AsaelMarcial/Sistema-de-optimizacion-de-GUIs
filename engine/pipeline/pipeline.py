from __future__ import annotations

from typing import Any

from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.debug_trace import DebugTrace
from engine.pipeline.result import PipelineResult
from engine.pipeline.stage_contract import PipelineContractError, StageContract, validate_produces, validate_requires
from engine.pipeline.stages.assemble_results import CONTRACT as ASSEMBLE_RESULTS_CONTRACT
from engine.pipeline.stages.assemble_results import run_stage as run_assemble_results_stage
from engine.pipeline.stages.assess_original_environmental_impact import (
    CONTRACT as ASSESS_ORIGINAL_ENVIRONMENTAL_IMPACT_CONTRACT,
)
from engine.pipeline.stages.assess_original_environmental_impact import (
    run_stage as run_assess_original_environmental_impact_stage,
)
from engine.pipeline.stages.assess_transformed_environmental_impact import (
    CONTRACT as ASSESS_TRANSFORMED_ENVIRONMENTAL_IMPACT_CONTRACT,
)
from engine.pipeline.stages.assess_transformed_environmental_impact import (
    run_stage as run_assess_transformed_environmental_impact_stage,
)
from engine.pipeline.stages.build_color_scheme import CONTRACT as BUILD_COLOR_SCHEME_CONTRACT
from engine.pipeline.stages.build_color_scheme import run_stage as run_build_color_scheme_stage
from engine.pipeline.stages.build_contrast_report import (
    CONTRACT as BUILD_CONTRAST_REPORT_CONTRACT,
)
from engine.pipeline.stages.build_contrast_report import (
    run_stage as run_build_contrast_report_stage,
)
from engine.pipeline.stages.capture_original_state import CONTRACT as CAPTURE_ORIGINAL_STATE_CONTRACT
from engine.pipeline.stages.capture_original_state import run_stage as run_capture_original_state_stage
from engine.pipeline.stages.close_page_builder import CONTRACT as CLOSE_PAGE_BUILDER_CONTRACT
from engine.pipeline.stages.close_page_builder import run_stage as run_close_page_builder_stage
from engine.pipeline.stages.prepare_project_session import CONTRACT as PREPARE_PROJECT_SESSION_CONTRACT
from engine.pipeline.stages.prepare_project_session import run_stage as run_prepare_project_session_stage
from engine.pipeline.stages.start_page_builder import CONTRACT as START_PAGE_BUILDER_CONTRACT
from engine.pipeline.stages.start_page_builder import run_stage as run_start_page_builder_stage
from engine.pipeline.stages.set_tokens import CONTRACT as SET_TOKENS_CONTRACT
from engine.pipeline.stages.set_tokens import run_stage as run_set_tokens_stage
from engine.pipeline.stages.check_tokens import CONTRACT as CHECK_TOKENS_CONTRACT
from engine.pipeline.stages.check_tokens import run_stage as run_check_tokens_stage
from engine.pipeline.stages.transform_source_project import CONTRACT as TRANSFORM_SOURCE_PROJECT_CONTRACT
from engine.pipeline.stages.transform_source_project import run_stage as run_transform_source_project_stage

_STAGES: tuple[tuple[StageContract, Any], ...] = (
    (START_PAGE_BUILDER_CONTRACT, run_start_page_builder_stage),
    (CAPTURE_ORIGINAL_STATE_CONTRACT, run_capture_original_state_stage),
    (BUILD_COLOR_SCHEME_CONTRACT, run_build_color_scheme_stage),
    (BUILD_CONTRAST_REPORT_CONTRACT, run_build_contrast_report_stage),
    (
        ASSESS_ORIGINAL_ENVIRONMENTAL_IMPACT_CONTRACT,
        run_assess_original_environmental_impact_stage,
    ),
    (SET_TOKENS_CONTRACT, run_set_tokens_stage),
    (CHECK_TOKENS_CONTRACT, run_check_tokens_stage),
    (TRANSFORM_SOURCE_PROJECT_CONTRACT, run_transform_source_project_stage),
    (
        ASSESS_TRANSFORMED_ENVIRONMENTAL_IMPACT_CONTRACT,
        run_assess_transformed_environmental_impact_stage,
    ),
    (CLOSE_PAGE_BUILDER_CONTRACT, run_close_page_builder_stage),
    (ASSEMBLE_RESULTS_CONTRACT, run_assemble_results_stage),
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


def run_pipeline(file) -> tuple[dict[str, Any] | None, str | None]:
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
    return PipelineResult(payload=context.get(K.RESULTS), error=context.error).to_tuple()
