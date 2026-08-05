from flask import (
    abort,
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from engine.adapters.file_system.file_manager import create_output_bundle
from engine.domain.models.session import Session
from engine.pipeline.pipeline import run_pipeline


main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/header")
def header():
    return render_template("header.html")


@main.route("/sessions/<session_id>/artifacts/<path:filename>")
def session_artifact(session_id: str, filename: str):
    artifacts_dir = (Session.SESSIONS_ROOT / session_id / "artifacts").resolve()
    return send_from_directory(artifacts_dir, filename)


@main.route("/sessions/<session_id>/after/<path:filename>")
def session_after(session_id: str, filename: str):
    after_dir = (Session.SESSIONS_ROOT / session_id / "after").resolve()
    return send_from_directory(after_dir, filename)


@main.route("/sessions/<session_id>/download")
def session_after_download(session_id: str):
    sessions_root = Session.SESSIONS_ROOT.resolve()
    session_dir = (sessions_root / session_id).resolve()

    try:
        session_dir.relative_to(sessions_root)
    except ValueError:
        abort(404)

    after_dir = (session_dir / "after").resolve()

    try:
        after_dir.relative_to(session_dir)
    except ValueError:
        abort(404)

    if not after_dir.is_dir():
        abort(404)

    if not any(path.is_file() for path in after_dir.rglob("*")):
        abort(404)

    artifacts_dir = (session_dir / "artifacts").resolve()
    zip_path = artifacts_dir / "glow_design.zip"

    if not zip_path.is_file():
        create_output_bundle(
            source_dir=after_dir,
            bundle_dir=artifacts_dir,
            bundle_name="glow_design.zip",
        )

    return send_from_directory(
        artifacts_dir,
        "glow_design.zip",
        as_attachment=True,
        download_name="glow_design.zip",
    )


@main.route("/results", methods=["POST"])
def results():
    files = request.files.getlist("file")
    payload, error_message = run_pipeline(files)
    if error_message:
        flash(error_message, "error")
        return redirect(url_for("main.index"))

    results = (payload or {}).get("results")
    summary = (payload or {}).get("summary")

    if results and results.get("session_dirname"):
        results["download_url"] = url_for(
            "main.session_after_download",
            session_id=results["session_dirname"],
        )

    return render_template("results.html", results=results, summary=summary)
