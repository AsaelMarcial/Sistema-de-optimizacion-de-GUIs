from __future__ import annotations

import os
import shutil

from flask import url_for

from engine.pipeline.context import PipelineContext


def _create_output_bundle(
    output_dir: str,
    artifacts_dir: str,
    session_id: str,
    session_dirname: str,
) -> tuple[str, str]:
    bundle_base = os.path.join(artifacts_dir, f"{session_id}_bundle")
    temp_zip_path = f"{bundle_base}.zip"
    shutil.make_archive(bundle_base, "zip", output_dir)
    final_zip_path = os.path.join(output_dir, f"{session_dirname}.zip")
    shutil.move(temp_zip_path, final_zip_path)
    return final_zip_path, os.path.basename(final_zip_path)


def bundle_outputs(context: PipelineContext) -> None:
    context.zip_output_path, context.zip_filename = _create_output_bundle(
        output_dir=context.output_dir or "",
        artifacts_dir=context.artifacts_dir or "",
        session_id=context.session_id or "",
        session_dirname=context.session_dirname or "",
    )
    context.zip_download_url = url_for(
        "main.session_output",
        session_id=context.session_dirname,
        filename=context.zip_filename,
    )
    context.trace.add_step("transformed.zip_created", {"zip_output_path": context.zip_output_path})
