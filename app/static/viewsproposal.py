"""from datetime import timedelta
from uuid import uuid4
from flask import (
    abort,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask.views import MethodView
from cache import ContextCache
from context import PipelineContext
from errors import FileValidationError

context_cache = ContextCache[PipelineContext](timeout=timedelta(minutes=40))


class IndexView(MethodView):
    def get(self):
        return render_template("index.html")

    def post(self):
        files = request.files.getlist("file")
        with PipelineContext() as context:
            state = pipeline(files, return_state=True)
        except Exception:
            # Si el pipeline falla, no dejamos un resultado inválido
            # almacenado en caché. Esto hay que ponerlo en el exit de PipelineContext
            context_cache.delete(run_id)
            raise
        return redirect(url_for("results", run_id=run_id))


class ResultsView(MethodView):
    def _get_context(self, run_id: str) -> PipelineContext:
        context = context_cache.get(run_id)
        if context is None:
            abort(404)
        g.context = context
        return context

    def get(self, run_id: str):
        context = self._get_context(run_id)
        #Habría que ajustarlo a lo que sí usa nuestro results.html
        return render_template(
            "results.html",
            context=context,
            results=context.results,
            color_scheme=context.color_scheme,
            prototype_structure=context.prototype_structure,
            quality_inputs=context.quality_inputs,
            download_url=url_for(
                "results",
                run_id=run_id,
            ),
        )

    def post(self, run_id: str):
        context = self._get_context(run_id)
        if context.result_file is None:
            abort(404)
        return send_file(
            context.result_file,
            as_attachment=True,
        )

app = Flask(
    _name_,
    static_folder="static",
    template_folder="templates",
)
app.add_url_rule(
    "/",
    endpoint="index",
    view_func=IndexView.as_view("index"),
)
app.add_url_rule(
    "/results/<run_id>",
    endpoint="results",
    view_func=ResultsView.as_view("results"),
    methods=["GET", "POST"],
)

@app.errorhandler(Exception)
def handle_exception(error):
    app.logger.exception("Unhandled exception")
    return render_template(
        "error.html",
        error=error,
    ), 500"""
