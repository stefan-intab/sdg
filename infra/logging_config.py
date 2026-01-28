# app/libs/logger.py
import logging
from typing import Optional

import config

LOOKUP_LEVEL = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "ERROR": logging.ERROR}


def configure_logging(
    service_name: Optional[str] = None,
    level: Optional[int] = None,  # Overrides environment level
) -> logging.Logger:
    """
    Create a per-service logger with a single StreamHandler, no propagation,
    and optional filter to drop /health lines. Also attaches the filter to
    uvicorn.access so access logs for /health are dropped too.
    """
    name = service_name or config.SERVICE_NAME
    
    effective_level: int
    if level is not None:
        effective_level = level
    else:
        level_name = config.LOG_LEVEL
        effective_level = LOOKUP_LEVEL.get(level_name, logging.INFO)
    
    logger = logging.getLogger(name)
    logger.setLevel(effective_level)
    
    logger.propagate = False  # avoid double emission via root/uvicorn

    # Ensure exactly one stream handler for this logger (idempotent)
    handler_id = f"{name}-stream"
    have_handler = any(getattr(h, "name", "") == handler_id for h in logger.handlers)
    if not have_handler:
        h = logging.StreamHandler()
        h.setLevel(effective_level)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
        try:
            h.name = handler_id
            logger.addHandler(h)
        except Exception:
            pass

    # Tame uvicorn loggers to avoid duplicates and drop health access lines
    for n in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        ul = logging.getLogger(n)
        ul.propagate = False

    return logger


app_logger = configure_logging()
