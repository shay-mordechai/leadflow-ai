import multiprocessing

# Worker Config
# For heavy CPU tasks (like Whisper) mixed with Async, we often want fewer workers
# to prevent RAM exhaustion, but enough to handle I/O.
# Formula: (2 x Num_Cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"

# Resilience settings
keepalive = 5
timeout = 120 # Higher timeout for potential slow AI operations if not backgrounded
worker_connections = 1000

# Binding
bind = "0.0.0.0:8000"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "warning" # Reduce log noise in production
