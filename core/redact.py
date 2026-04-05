"""
Secret Redaction Utility for MultiCode.

Masks sensitive data in logs, output, and audit trails.
Ensures API keys, tokens, credentials, and PII are never
exposed in plaintext.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class RedactionRule:
    """A pattern-based redaction rule."""
    name: str
    pattern: re.Pattern
    replacement: str
    priority: int = 0  # Higher = applied first


# Built-in redaction rules
DEFAULT_RULES: list[RedactionRule] = [
    RedactionRule(
        name="openrouter_api_key",
        pattern=re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
        replacement="sk-or-v1-****[REDACTED]",
        priority=100,
    ),
    RedactionRule(
        name="openrouter_api_key_partial",
        pattern=re.compile(r"sk-or-[A-Za-z0-9]{8,}"),
        replacement="sk-or-****[REDACTED]",
        priority=100,
    ),
    RedactionRule(
        name="github_token",
        pattern=re.compile(r"ghp_[A-Za-z0-9]{36}"),
        replacement="ghp_****[REDACTED]",
        priority=100,
    ),
    RedactionRule(
        name="github_oauth_token",
        pattern=re.compile(r"gho_[A-Za-z0-9]{36}"),
        replacement="gho_****[REDACTED]",
        priority=100,
    ),
    RedactionRule(
        name="github_app_token",
        pattern=re.compile(r"ghu_[A-Za-z0-9]{36}"),
        replacement="ghu_****[REDACTED]",
        priority=100,
    ),
    RedactionRule(
        name="github_refresh_token",
        pattern=re.compile(r"ghr_[A-Za-z0-9]{36}"),
        replacement="ghr_****[REDACTED]",
        priority=100,
    ),
    RedactionRule(
        name="github_pat_token",
        pattern=re.compile(r"github_pat_[A-Za-z0-9_]{80,}"),
        replacement="github_pat_****[REDACTED]",
        priority=100,
    ),
    RedactionRule(
        name="aws_access_key",
        pattern=re.compile(r"AKIA[0-9A-Z]{16}"),
        replacement="AKIA****[REDACTED]",
        priority=100,
    ),
    RedactionRule(
        name="aws_secret_key",
        pattern=re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?"),
        replacement="aws_secret_access_key: ****[REDACTED]",
        priority=95,
    ),
    RedactionRule(
        name="jwt_token",
        pattern=re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        replacement="****[JWT_REDACTED]****",
        priority=95,
    ),
    RedactionRule(
        name="private_key_pem",
        pattern=re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----[A-Za-z0-9+/=\s]+-----END\s+(RSA\s+)?PRIVATE\s+KEY-----"),
        replacement="-----BEGIN PRIVATE KEY-----\\n****[PRIVATE_KEY_REDACTED]\\n-----END PRIVATE KEY-----",
        priority=95,
    ),
    RedactionRule(
        name="private_key_header",
        pattern=re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"),
        replacement="-----BEGIN PRIVATE KEY----- [REDACTED]",
        priority=90,
    ),
    RedactionRule(
        name="bearer_token",
        pattern=re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"),
        replacement="Bearer ****[REDACTED]",
        priority=90,
    ),
    RedactionRule(
        name="authorization_header",
        pattern=re.compile(r"(Authorization['\"]?\s*[:=]\s*['\"]?)[^'\"]+(['\"]?)"),
        replacement=r"\1****[REDACTED]\2",
        priority=90,
    ),
    RedactionRule(
        name="api_key_in_json",
        pattern=re.compile(r"(['\"]api_key['\"])\s*:\s*['\"]([^'\"]+)['\"]"),
        replacement=r'\1: "****[REDACTED]"',
        priority=80,
    ),
    RedactionRule(
        name="password_field",
        pattern=re.compile(r"(password|passwd|pwd|secret|token)['\"]?\s*[:=]\s*['\"]?[^'\s,}\]]+"),
        replacement=r'\1: "****[REDACTED]"',
        priority=85,
    ),
    RedactionRule(
        name="email_address",
        pattern=re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        replacement="***[EMAIL_REDACTED]***",
        priority=50,
    ),
    RedactionRule(
        name="ipv4_address",
        pattern=re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        replacement="***[IP_REDACTED]***",
        priority=40,
    ),
    RedactionRule(
        name="file_path_windows",
        pattern=re.compile(r"[A-Z]:\\Users\\[^\\]+"),
        replacement=r"C:\Users\***[USER_REDACTED]***",
        priority=30,
    ),
    RedactionRule(
        name="file_path_home",
        pattern=re.compile(r"/home/[^/]+"),
        replacement=r"/home/***[USER_REDACTED]***",
        priority=30,
    ),
]


class Redactor:
    """
    Applies redaction rules to text output.

    Usage:
        redactor = Redactor()
        safe_text = redactor.redact("API key: sk-or-v1-abc123...")
    """

    def __init__(self, rules: list[RedactionRule] | None = None):
        self._rules = sorted(
            rules if rules is not None else DEFAULT_RULES,
            key=lambda r: r.priority,
            reverse=True,
        )

    def redact(self, text: str) -> str:
        """Apply all redaction rules to the given text."""
        if not text:
            return text
        result = text
        for rule in self._rules:
            # Use lambda-based replacement to avoid backslash escaping issues
            result = rule.pattern.sub(lambda m, r=rule.replacement: r, result)
        return result

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Redact all string values in a dictionary."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.redact(value)
            elif isinstance(value, dict):
                result[key] = self.redact_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.redact(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def add_rule(self, rule: RedactionRule) -> None:
        """Add a custom redaction rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)


# Global redactor instance
_redactor: Redactor | None = None


def get_redactor() -> Redactor:
    """Get or create the global redactor instance."""
    global _redactor
    if _redactor is None:
        _redactor = Redactor()
    return _redactor


def redact(text: str) -> str:
    """Quick redaction using the global redactor."""
    return get_redactor().redact(text)


def reset_redactor() -> None:
    """Reset the global redactor (for testing)."""
    global _redactor
    _redactor = None
