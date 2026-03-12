"""Legacy compatibility wrapper.

Prefer using `run.py` as the application entrypoint.
"""

from run import app


if __name__ == "__main__":
    app.run(debug=True)
