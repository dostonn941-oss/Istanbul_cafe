import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from istanbul_cafe_bot import app, flask_app

# Vercel WSGI & ASGI entrypoints
app = flask_app
application = flask_app
handler = flask_app

if __name__ == "__main__":
    app.run()
