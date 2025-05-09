from flask import Flask
from config import MAX_CONTENT_LENGTH
from routes.main_routes import main

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Registrar Blueprint
app.register_blueprint(main)

if __name__ == "__main__":
    app.run(debug=True)