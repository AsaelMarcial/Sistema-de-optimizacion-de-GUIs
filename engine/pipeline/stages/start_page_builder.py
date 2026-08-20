from __future__ import annotations

import posixpath
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.source_code_handler.local_asset_rewriter import (
    rewrite_local_asset_references,
)
from engine.pipeline.context import PipelineContext
from engine.pipeline.glow_runtime import glow_flow, glow_task
from prefect.states import Completed, Failed, State


@glow_task
def _page_builder_ready(
    page_builder: PageBuilder | None,
) -> State:
    if page_builder is None:
        return Failed(message="PageBuilder no fue inicializado.")

    try:
        document_root = page_builder.document_root

        if (
            page_builder.is_open
            and page_builder.html_path is not None
            and page_builder.html_path.is_file()
            and page_builder.base_path is not None
            and page_builder.base_path.is_dir()
            and document_root is not None
            and bool(document_root)
        ):
            return Completed(message="PageBuilder esta listo.")
        return Failed(message="PageBuilder no quedo listo.")

    except (
        AttributeError,
        RuntimeError,
        OSError,
    ):
        return Failed(message="No se pudo validar PageBuilder.")


@glow_flow
def start_page_builder(
    context: PipelineContext,
):
    session = context.session
    html_files = session.get_by_type(".html")

    if len(html_files) != 1:
        raise RuntimeError(
            "Se esperaba exactamente un archivo HTML "
            "con el sufijo 'before'."
        )

    html_file = html_files[0]
    before_root = session.get_area_root("before")
    rewritten_values = rewrite_local_asset_references(html_file, session)
    if rewritten_values:
        print({
            "html.asset_paths_rewritten": {
                "rewrite_count": len(rewritten_values),
                "html_path": str(html_file),
            }
        })

    styles = context.style
    request_records = context.request_records
    styles.clear()
    request_records.clear()
    page_builder = PageBuilder(
        styles=styles,
        request_records=request_records,
    )

    try:
        page_builder.load_page(html_file, project_root=before_root)
        network_information = page_builder.get_network_asset_information()
        network_by_url: dict[str, dict] = {}
        for item in network_information:
            request = item.get("request") or {}
            response_event = item.get("responseReceived") or {}
            response = response_event.get("response") or {}
            for url in {
                str(request.get("url") or ""),
                str(response.get("url") or ""),
            }:
                if not url:
                    continue
                network_by_url[url] = item
                network_by_url[unquote(url)] = item

        matched_network_ids: set[str] = set()
        for source in session.get_all_sources():
            if isinstance(source.source_name, Path):
                runtime_source = urljoin(
                    page_builder.page_url,
                    quote(source.source_name.as_posix(), safe="/:@%"),
                )
            else:
                runtime_source = str(source.source_name)

            source.runtime_source = runtime_source
            network_item = network_by_url.get(runtime_source) or network_by_url.get(unquote(runtime_source))
            if network_item is None:
                continue

            matched_network_ids.add(str(network_item.get("requestId") or ""))
            source.set_load_status(
                network_item.get("load_status"),
                network_item.get("error_message"),
            )

        for item in network_information:
            request_id = str(item.get("requestId") or "")
            if request_id in matched_network_ids:
                continue

            request = item.get("request") or {}
            response_event = item.get("responseReceived") or {}
            response = response_event.get("response") or {}
            runtime_source = str(request.get("url") or response.get("url") or "")
            if not runtime_source:
                continue

            parsed_runtime_source = urlparse(runtime_source)
            parsed_page_url = urlparse(page_builder.page_url)
            source_name = runtime_source
            if parsed_runtime_source.netloc == parsed_page_url.netloc:
                source_name = Path(
                    posixpath.relpath(
                        unquote(parsed_runtime_source.path),
                        posixpath.dirname(unquote(parsed_page_url.path)),
                    )
                )

            session.register_source(
                source_name,
                founded_on="network",
                load_status=item.get("load_status"),
                error_message=item.get("error_message"),
                runtime_source=runtime_source,
            )

        context.set("page_builder", page_builder)

        stylesheet_count = len(
            page_builder.styles.stylesheets
        )

        print({
            "start_page_builder.complete": {
                "html_path": str(
                    page_builder.html_path
                ),
                "base_path": str(
                    page_builder.base_path
                ),
                "document_node_id": (
                    page_builder.document_root
                ),
                "stylesheets": stylesheet_count,
            }
        })
        return _page_builder_ready(context.page_builder, return_state=True)

    except Exception as exc:
        try:
            page_builder.close()
        except Exception:
            pass

        raise RuntimeError(
            f"unexpected error [{type(exc).__name__}]: {exc}"
        ) from exc
