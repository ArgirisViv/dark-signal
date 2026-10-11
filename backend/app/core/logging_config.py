"""
Logging configuration for the Phishing Simulator application.
Provides structured logging with JSON formatting for production use.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Any, Dict
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that adds timestamp and level name."""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name


def setup_logging(level: str = "INFO") -> None:
    """
    Configure application-wide logging.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    
    # Console handler with JSON formatting
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
    )
    root_logger.addHandler(console_handler)
    
    # Suppress noisy loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# Security audit logger for sensitive operations
security_logger = logging.getLogger("security_audit")


def log_security_event(event_type: str, user_id: str, action: str, details: Dict[str, Any] = None) -> None:
    """
    Log security-relevant events for audit trail.
    
    Args:
        event_type: Type of security event (LOGIN, LOGOUT, FAILED_AUTH, PERMISSION_DENIED, etc.)
        user_id: ID of the user involved
        action: Description of the action
        details: Additional context details
    """
    log_data = {
        "event_type": event_type,
        "user_id": user_id,
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if details:
        log_data.update(details)
    
    security_logger.info(json.dumps(log_data))
