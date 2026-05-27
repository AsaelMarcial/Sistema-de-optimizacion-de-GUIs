from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from pathlib import Path

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
    artifacts_dir = (Path("sessions") / session_id / "artifacts").resolve()
    return send_from_directory(artifacts_dir, filename)


@main.route("/sessions/<session_id>/after/<path:filename>")
def session_after(session_id: str, filename: str):
    after_dir = (Path("sessions") / session_id / "after").resolve()
    return send_from_directory(after_dir, filename)


@main.route("/results", methods=["POST"])
def results():
    file = request.files.get("file")
    results, error_message = run_pipeline(file)
    if error_message:
        flash(error_message, "error")
        return redirect(url_for("main.index"))

    if results and results.get("session_dirname") and results.get("download_url"):
        results["download_url"] = url_for(
            "main.session_artifact",
            session_id=results["session_dirname"],
            filename=str(results["download_url"]).rsplit("/", 1)[-1],
        )

    return render_template("results.html", results=results)
