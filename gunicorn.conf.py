"""
Gunicorn configuration for production deployment.
https://docs.gunicorn.org/en/stable/settings.html
"""

import os
import multiprocessing

# ---------- Server socket ----------
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# ---------- Workers ----------
# Render free tier has 512 MB RAM — keep workers low.
# Rule of thumb: (2 × CPU cores) + 1, but cap at 4 for small instances.
workers = int(os.environ.get("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 4)))
worker_class = "gthread"       # threaded workers (good for I/O-bound apps)
threads = 2                    # threads per worker
worker_tmp_dir = "/dev/shm"   # faster heartbeat on Linux (tmpfs)

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
preload_app = True             # load app before forking workers (saves RAM)
