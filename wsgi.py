"""
WSGI entry point for production deployment.
Used by gunicorn / Render / any WSGI server.

    gunicorn wsgi:app
"""

from run import app  # noqa: F401
