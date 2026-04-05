"""
Structured Audit Logging for MultiCode.

Provides immutable, append-only JSONL audit trails for compliance.
Every significant action is logged with a structured schema that
includes timestamps, session IDs, agent attribution, and cost data.

Audit events are redacted of secrets before writing.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from core.redact import redact as _redact_text

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Types of audit events."""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TASK_CLASSIFIED = "task_classified"
    AGENT_SPAWNED = "agent_spawned"
    AGENT_COMPLETED = "agent_completed"
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_READ = "file_read"
    SHELL_COMMAND = "shell_command"
    API_CALL = "api_call"
    VOTE_CAST = "vote_cast"
    CONSENSUS_REACHED = "consensus_reached"
    CONSENSUS_FAILED = "consensus_failed"
    COST_WARNING = "cost_warning"
    QUOTA_EXCEEDED = "quota_exceeded"
    MEMORY_LOADED = "memory_loaded"
    MEMORY_SAVED = "memory_saved"
    CONFIG_CHANGED = "config_changed"
    ERROR = "error"


@dataclass
class AuditEvent:
    """
    A single structured audit event.

    Schema:
        timestamp: ISO-8601 UTC timestamp
        session_id: Unique session identifier
        action: Type of action (AuditAction)
        agent: Agent name (if applicable)
        detail: Redacted event details (dict)
        input_hash: Hash of user input (for attribution without content)
        tokens_used: Token count for this action
        cost_estimate_usd: Estimated cost in USD
        files_affected: List of file paths touched
    """
    session_id: str
    action: AuditAction
    agent: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    input_hash: str | None = None
    tokens_used: int = 0
    cost_estimate_usd: float = 0.0
    files_affected: list[str] = field(default_factory=list)
    # Auto-populated
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["action"] = self.action.value
        return d

    def to_json(self) -> str:
        """Serialize to a single JSON line (JSONL format)."""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_json(cls, line: str) -> AuditEvent:
        """Deserialize from a JSONL line."""
        data = json.loads(line)
        data["action"] = AuditAction(data["action"])
        return cls(**data)


class AuditSink:
    """Pluggable output destination for audit events."""

    def write(self, event: AuditEvent) -> None:
        """Write a single audit event."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the sink (release resources)."""
        pass


class FileAuditSink(AuditSink):
    """Writes audit events to an append-only JSONL file."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: AuditEvent) -> None:
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")


class StdoutAuditSink(AuditSink):
    """Writes audit events to stdout (for development/testing)."""

    def write(self, event: AuditEvent) -> None:
        print(event.to_json(), flush=True)


class AuditLogger:
    """
    Central audit logger that writes structured, redacted events.

    Usage:
        audit = AuditLogger(session_id="abc123")
        audit.log(AuditAction.SESSION_START, detail={"mode": "complex"})
        audit.log(AuditAction.AGENT_SPAWNED, agent="Engineer")
    """

    def __init__(
        self,
        session_id: str,
        sink: AuditSink | None = None,
        enable_redaction: bool = True,
    ):
        self.session_id = session_id
        self._sink = sink
        self._enable_redaction = enable_redaction
        self._events: list[AuditEvent] = []

    def set_sink(self, sink: AuditSink) -> None:
        """Set or change the audit sink."""
        self._sink = sink

    def log(
        self,
        action: AuditAction,
        agent: str | None = None,
        detail: dict[str, Any] | None = None,
        input_hash: str | None = None,
        tokens_used: int = 0,
        cost_estimate_usd: float = 0.0,
        files_affected: list[str] | None = None,
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            action: Type of action
            agent: Agent name (if applicable)
            detail: Additional context (will be redacted)
            input_hash: Hash of user input for attribution
            tokens_used: Token count for this action
            cost_estimate_usd: Estimated cost in USD
            files_affected: List of files touched

        Returns:
            The created AuditEvent
        """
        detail = detail or {}
        files = files_affected or []

        # Redact sensitive data from detail
        if self._enable_redaction:
            detail = _redact_dict(detail)

        event = AuditEvent(
            session_id=self.session_id,
            action=action,
            agent=agent,
            detail=detail,
            input_hash=input_hash,
            tokens_used=tokens_used,
            cost_estimate_usd=cost_estimate_usd,
            files_affected=files,
        )

        self._events.append(event)

        # Write to sink
        if self._sink:
            try:
                self._sink.write(event)
            except Exception as e:
                logger.error("Audit sink write failed: %s", e)

        # Also log to standard logger for visibility
        logger.info(
            "[AUDIT] %s | %s | agent=%s | tokens=%d | cost=$%.4f",
            action.value,
            event.event_id,
            agent or "N/A",
            tokens_used,
            cost_estimate_usd,
        )

        return event

    def get_events(
        self,
        action_filter: AuditAction | None = None,
        agent_filter: str | None = None,
    ) -> list[AuditEvent]:
        """Get logged events with optional filtering."""
        events = self._events
        if action_filter:
            events = [e for e in events if e.action == action_filter]
        if agent_filter:
            events = [e for e in events if e.agent == agent_filter]
        return events

    def get_total_cost(self) -> float:
        """Get total estimated cost for this session."""
        return sum(e.cost_estimate_usd for e in self._events)

    def get_total_tokens(self) -> int:
        """Get total tokens used for this session."""
        return sum(e.tokens_used for e in self._events)

    def export(self) -> list[dict[str, Any]]:
        """Export all events as a list of dictionaries."""
        return [e.to_dict() for e in self._events]

    def close(self) -> None:
        """Close the audit logger and sink."""
        if self._sink:
            self._sink.close()


def _redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive strings from a dictionary."""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = _redact_text(value)
        elif isinstance(value, dict):
            result[key] = _redact_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _redact_text(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


# Global audit logger factory
def create_audit_logger(
    session_id: str,
    log_path: Path | None = None,
    enable_redaction: bool = True,
) -> AuditLogger:
    """
    Create a new audit logger for a session.

    Args:
        session_id: Unique session identifier
        log_path: Path to JSONL audit log (None = no file sink)
        enable_redaction: Whether to redact sensitive data

    Returns:
        Configured AuditLogger instance
    """
    logger_obj = AuditLogger(
        session_id=session_id,
        enable_redaction=enable_redaction,
    )

    # Set file sink if path provided
    if log_path:
        logger_obj.set_sink(FileAuditSink(log_path))

    return logger_obj


__all__ = [
    "AuditAction",
    "AuditEvent",
    "AuditLogger",
    "AuditSink",
    "FileAuditSink",
    "StdoutAuditSink",
    "create_audit_logger",
]
