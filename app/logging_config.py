"""Logging configuration for Rule Intelligence Engine."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def setup_logging():
    """Configure logging for the application."""
    # Create logs directory if it doesn't exist
    logs_dir = Path("/tmp/rie_logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Set up formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Set up file handler with rotation
    file_handler = RotatingFileHandler(
        logs_dir / 'app.log',
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Suppress overly verbose libraries
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)


# Input validation logger
input_validation_logger = get_logger('input_validation')

# Preprocessing logger
preprocessing_logger = get_logger('preprocessing')
