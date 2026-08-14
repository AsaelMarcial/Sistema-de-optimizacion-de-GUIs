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
from engine.domain.enums.scope.context_keys import ContextKey as K
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
    context, error_message = run_pipeline(files)
    if error_message:
        flash(error_message, "error")
        return redirect(url_for("main.index"))
    if context is None:
        flash("No se pudieron generar resultados.", "error")
        return redirect(url_for("main.index"))

    session = context.get(K.SESSION)
    dom_tree = context.get(K.DOM_TREE)
    changed_elements = [
        element
        for element in (dom_tree.iter_dfs() if dom_tree is not None else ())
        if any(property_model.has_changed for property_model in element.properties)
    ]

    return render_template(
        "results.html",
        context=context,
        session=session,
        session_dirname=session.session_dir.name,
        summary=context.get(K.SUMMARY),
        dom_tree=dom_tree,
        changed_elements=changed_elements,
        color_scheme=context.get(K.COLOR_SCHEME),
        before_assessment=context.get(K.ENVIRONMENTAL_BEFORE_ASSESSMENT),
        after_assessment=context.get(K.ENVIRONMENTAL_AFTER_ASSESSMENT),
        savings=context.get(K.ENVIRONMENTAL_SAVINGS),
        download_url=url_for(
            "main.session_after_download",
            session_id=session.session_dir.name,
        ),
    )
