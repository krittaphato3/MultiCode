"""Tests for the redaction module."""


from core.redact import redact, reset_redactor


class TestRedaction:
    """Test secret redaction rules."""

    def setup_method(self):
        """Reset redactor before each test."""
        reset_redactor()

    def test_redact_openrouter_api_key(self):
        """OpenRouter API keys should be redacted."""
        text = "My key is sk-or-v1-abcdefghijklmnopqrstuvwxyz123456"
        result = redact(text)
        assert "sk-or-v1-abcdefghijklmnopqrstuvwxyz123456" not in result
        assert "[REDACTED]" in result

    def test_redact_github_token(self):
        """GitHub tokens should be redacted."""
        text = "Token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef1234"
        result = redact(text)
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef1234" not in result
        assert "[REDACTED]" in result

    def test_redact_aws_access_key(self):
        """AWS access keys should be redacted."""
        text = "Access key: AKIAIOSFODNN7EXAMPLE"
        result = redact(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED]" in result

    def test_redact_jwt_token(self):
        """JWT tokens should be redacted."""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        text = f"Bearer {jwt}"
        result = redact(text)
        assert jwt not in result
        assert "[JWT_REDACTED]" in result

    def test_redact_private_key(self):
        """PEM private keys should be redacted."""
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF\n-----END RSA PRIVATE KEY-----"
        result = redact(text)
        assert "MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF" not in result
        assert "[REDACTED]" in result

    def test_redact_email(self):
        """Email addresses should be redacted."""
        text = "Contact user@example.com for help"
        result = redact(text)
        assert "user@example.com" not in result
        assert "[EMAIL_REDACTED]" in result

    def test_redact_ipv4(self):
        """IPv4 addresses should be redacted."""
        text = "Server at 192.168.1.100"
        result = redact(text)
        assert "192.168.1.100" not in result
        assert "[IP_REDACTED]" in result

    def test_redact_password_field(self):
        """Password fields should be redacted."""
        text = 'password: "mysecretpassword123"'
        result = redact(text)
        assert "mysecretpassword123" not in result
        assert "[REDACTED]" in result

    def test_no_redaction_on_safe_text(self):
        """Safe text should not be redacted."""
        text = "Hello world, this is a test"
        result = redact(text)
        assert result == text

    def test_redact_bearer_token(self):
        """Bearer tokens should be redacted."""
        text = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890"
        result = redact(text)
        assert "abcdefghijklmnopqrstuvwxyz1234567890" not in result
        assert "[REDACTED]" in result
