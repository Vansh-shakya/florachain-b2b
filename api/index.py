import sys
import os

# Add the repository root directory to sys.path so 'app' can be imported reliably
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app

# Vercel's Python runtime discovers and executes the WSGI application via this 'app' object
app = create_app()

