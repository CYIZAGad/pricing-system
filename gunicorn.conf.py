"""
Gunicorn configuration for production deployment.
https://docs.gunicorn.org/en/stable/settings.html
"""

import os

# ---------- Server socket ----------
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# ---------- Workers ----------
# Render free tier has 512 MB RAM — keep workers low to avoid OOM restarts.
workers = int(os.environ.get("WEB_CONCURRENCY", 2))
worker_class = "gthread"       # threaded workers (good for I/O-bound apps)
threads = 2                    # threads per worker
worker_tmp_dir = "/dev/shm"   # faster heartbeat on Linux (tmpfs)
max_requests = 1000            # restart workers after N requests (prevent memory leaks)
max_requests_jitter = 50       # stagger restarts

# ---------- Timeouts ----------
timeout = 120                  # OCR processing can be slow
graceful_timeout = 30
keepalive = 5

# ---------- Logging ----------
accesslog = "-"                # stdout
errorlog = "-"                 # stderr
loglevel = os.environ.get("LOG_LEVEL", "info")

# ---------- Security ----------
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# ---------- Process naming ----------
proc_name = "pharmacy-pricing"

# ---------- Preload ----------
preload_app = False            # disabled: avoids crash-loop if app init fails
