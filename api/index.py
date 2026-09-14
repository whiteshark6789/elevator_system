import os
import sys
import traceback

# Add the root directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend'))

try:
    from backend.app import app
except Exception as e:
    from flask import Flask
    app = Flask(__name__)
    error_trace = traceback.format_exc()
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        return f"<h1>Initialization Error in Vercel</h1><pre>{error_trace}</pre>", 500
