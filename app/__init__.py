"""App package."""

import os

from flask import Flask

from app.config import MAX_CONTENT_LENGTH


def create_app():
    from app.routes import main

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    # Clave secreta segura generada con urandom
    app.secret_key = os.urandom(24)

    # Registrar Blueprint
    app.register_blueprint(main)

    return app
