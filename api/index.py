import os
import sys

# Add the root directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend'))

from backend.app import app

# Vercel requires the application instance to be named `app`
