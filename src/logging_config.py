# src/logging_config.py
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    """
    Configures a rotating file logger.
    Rotates logs when they reach 5MB, keeping the last 3 backup files.
    """
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 1. File Handler (Rotating)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024, # 5 MB
        backupCount=3
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # 2. Console Handler (for Docker/System logs)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Root Logger Config
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger