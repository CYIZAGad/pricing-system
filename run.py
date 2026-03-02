"""
Main entry point for the Pharmacy Pricing System
"""

from app import create_app
from config import Config
import logging
import os
import sys

# ---------- Logging configuration ----------
_log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
_handlers = [logging.StreamHandler(sys.stdout)]

# In production, also log to a rotating file (if writable)
if os.environ.get('FLASK_ENV') == 'production':
    try:
        from logging.handlers import RotatingFileHandler
        _fh = RotatingFileHandler('app.log', maxBytes=5_000_000, backupCount=3)
        _fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        _handlers.append(_fh)
    except Exception:
        pass  # file logging is best-effort

logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=_handlers
)

app = create_app(Config)

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
