from __future__ import annotations

from engine.adapters.source_code_handler.code_processor import (
    apply_tokens_to_project,
    evaluate_and_apply_heuristics,
)
from engine.adapters.file_system.file_manager import read_text
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import Session
from engine.domain.models.style import StyleCatalog
from engine.domain.models.token import TokenInventoryModel
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_transform(session: Session) -> bool:
    try:
        before_html = session.find_by_suffix("before", ("html",))
        after_html = session.find_by_suffix("after", ("html",))
        return len(before_html) == 1 and len(after_html) == 1 and before_html[0].exists() and after_html[0].exists()
    except (FileNotFoundError, RuntimeError, ValueError, OSError):
        return False


CONTRACT = StageContract(
    name="transform_source_project",
    requires=(
        context_value(K.SESSION, Session, validator=_session_ready_for_transform),
        context_value(K.PROTOTYPE_STRUCTURE, PrototypeStructure),
        context_value(K.STYLE_CATALOG, StyleCatalog),
        context_value(K.TOKEN_INVENTORY, TokenInventoryModel),
    ),
    produces=(
        context_value(K.TRANSFORMATION_HEURISTICS, list),
        context_value(K.TRANSFORMATION_OUTPUT_HTML_PATH, str, validator=lambda value: bool(value.strip())),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    session = context.get(K.SESSION)
    before_html = session.find_by_suffix("before", ("html",))[0]
    after_html = session.find_by_suffix("after", ("html",))[0]
    before_html_path = before_html
    after_html_path = after_html
    html_content = read_text(before_html_path)
    after_dir = session.get_area_root("after")
    after_project_root = session.get_area_root("after")
    context.trace.add_stage_event(CONTRACT.name, "start", {"after_dir": str(after_dir)})

    token_results = apply_tokens_to_project(
        html_content,
        after_html_path,
        after_project_root,
        context.get(K.TOKEN_INVENTORY),
        context.get(K.PROTOTYPE_STRUCTURE),
        context.get(K.STYLE_CATALOG),
    )
    if token_results:
        heuristics_results = token_results
    else:
        heuristics_results = evaluate_and_apply_heuristics(
            html_content,
            after_html_path,
            after_project_root,
            None,
        )
    context.set(K.TRANSFORMATION_HEURISTICS, heuristics_results)
    context.trace.add_step(
        "transformed.heuristics_applied",
        {"heuristics_count": len(heuristics_results)},
    )

    transformed_html_path = after_html_path
    context.set(K.TRANSFORMATION_OUTPUT_HTML_PATH, str(transformed_html_path))
    context.trace.add_step(
        "transformed.html_loaded",
        {"html_environmental_path": str(transformed_html_path)},
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "heuristics_count": len(heuristics_results),
            "transformed_html_path": str(transformed_html_path),
        },
    )
    return context
