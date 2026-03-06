import json
import logging
import uuid
from typing import Any


def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None:
    """Emit a structured JSON log with stable keys for correlation."""
    payload = {"event": event}
    payload.update({k: v for k, v in context.items() if v is not None})
    logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))


def emit_critical_alert(logger: logging.Logger, alert_code: str, message: str, **context: Any) -> str:
    """Emit a minimal high-visibility critical alert and return incident id."""
    incident_id = str(uuid.uuid4())
    log_event(
        logger,
        logging.CRITICAL,
        "critical_alert",
        alert_code=alert_code,
        message=message,
        incident_id=incident_id,
        **context,
    )
    return incident_id
