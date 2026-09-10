from __future__ import annotations

from bs4 import BeautifulSoup, Tag
from flask import g
import tinycss2

from engine.adapters.source_code_handler.local_asset_rewriter import (
    extract_reference_candidates,
)
from engine.domain.models.project_context import ProjectFile, ProjectSource
from engine.pipeline.glow_runtime import glow_flow


@glow_flow
def static_evaluation() -> None:
    g.style.clear()
    evaluated_files = _register_project_file_references()

    print(
        {
            "static_evaluation.complete": {
                "html_path": str(g.project_context.html.path),
                "asset_count": len(g.project_context),
                "evaluated_files": evaluated_files,
            }
        }
    )


def _register_project_file_references() -> int:
    pending = [g.project_context.html]
    evaluated: set[ProjectFile] = set()

    while pending:
        project_file = pending.pop(0)
        if project_file in evaluated or project_file.file_type not in {"html", "css"}:
            continue

        evaluated.add(project_file)
        for reference in _references_from_project_file(project_file):
            if not isinstance(project_file, ProjectSource):
                continue

            related_file = g.project_context.project_file(reference, project_file)
            if related_file is not None:
                project_file.add_dependency(related_file, reference)

            if related_file is not None and related_file.file_type == "css":
                pending.append(related_file)

    return len(evaluated)


def _references_from_project_file(
    project_file: ProjectFile,
) -> tuple[str, ...]:
    path = project_file.absolute_path
    if not path.is_file():
        return ()

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ()

    if project_file.file_type == "css":
        references: list[str] = []
        for rule in tinycss2.parse_stylesheet(
            text,
            skip_comments=True,
            skip_whitespace=True,
        ):
            prelude = getattr(rule, "prelude", None)
            if prelude:
                references.extend(
                    extract_reference_candidates(tinycss2.serialize(prelude))
                )

                if (
                    getattr(rule, "type", "") == "at-rule"
                    and getattr(rule, "lower_at_keyword", "") == "import"
                ):
                    references.extend(
                        str(token.value).strip()
                        for token in prelude
                        if getattr(token, "type", "") == "string"
                        and str(token.value).strip()
                    )

            content = getattr(rule, "content", None)
            if content:
                references.extend(
                    extract_reference_candidates(tinycss2.serialize(content))
                )

        return tuple(dict.fromkeys(references))

    soup = BeautifulSoup(text, "html.parser")
    references: list[str] = []
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue

        for attr_name, attr_value in tag.attrs.items():
            values = attr_value if isinstance(attr_value, list) else [attr_value]
            for value in values:
                references.extend(
                    extract_reference_candidates(
                        str(value),
                        attribute_name=attr_name,
                    )
                )

        if tag.name and tag.name.casefold() == "style" and tag.string is not None:
            references.extend(extract_reference_candidates(str(tag.string)))

    return tuple(references)
