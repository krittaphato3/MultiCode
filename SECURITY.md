# MultiCode Security Policy

## Security Features

### 1. API Key Protection
- ✅ Keys stored in OS keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- ✅ Fallback to obfuscated config file if keyring unavailable (XOR + base64 — not cryptographic)
- ✅ Never logged or displayed in full
- ✅ Masked in UI (shows first 15 and last 4 chars only)

### 2. Shell Command Safety
- ✅ Whitelist of allowed commands
- ✅ Blocklist of dangerous patterns
- ✅ User confirmation required for risky operations
- ✅ Command logging for audit trail
- ✅ Timeout protection (default 60s)
- ✅ No sudo/admin without explicit confirmation

### 3. File System Security
- ✅ Operations restricted to workspace directory
- ✅ Path traversal prevention (../.. blocked)
- ✅ Symlink following disabled by default
- ✅ File size limits (default 10MB)
- ✅ Extension filtering for executable files
- ✅ Backup before destructive operations

### 4. Input Validation
- ✅ All user input sanitized
- ✅ Command injection prevention
- ✅ SQL injection prevention (if applicable)
- ✅ XSS prevention in outputs

### 5. Network Security
- ✅ HTTPS-only API connections
- ✅ Certificate validation
- ✅ Rate limiting
- ✅ Request timeout

### 6. Audit & Logging
- ✅ All file operations logged
- ✅ All shell commands logged
- ✅ All API calls logged
- ✅ Security events highlighted
- ✅ Log rotation (max 10MB, keep 5 files)

### 7. Error Handling
- ✅ No sensitive data in error messages
- ✅ Stack traces hidden from users
- ✅ Graceful degradation
- ✅ Automatic retry with backoff

## Security Guidelines for Users

### DO:
- Keep your API key secure
- Review commands before confirming
- Keep MultiCode updated
- Report security issues responsibly

### DON'T:
- Share your API key
- Run MultiCode as admin/root
- Execute untrusted code
- Disable safety features

## Reporting Security Issues

**DO NOT** create public GitHub issues for security vulnerabilities.

Email: [Create issue privately](https://github.com/krittaphato3/MultiCode/security/advisories)

Or use GitHub Security Advisories (private):
1. Go to [Security tab](https://github.com/krittaphato3/MultiCode/security)
2. Click "Report a vulnerability"
3. Provide details privately

## Version Security Matrix

| Version | Security Updates | Status |
|---------|-----------------|--------|
| 0.2.x | Current | ✅ Supported |
| 0.1.x | Critical only | ⚠️ Legacy |
| < 0.1 | None | ❌ Unsupported |

## Security Audit Checklist

Before each release:
- [ ] Dependency audit (`pip audit`)
- [ ] Static analysis (`bandit -r .`)
- [ ] Secret scanning (no API keys in code)
- [ ] Permission review (minimum required)
- [ ] Log review (no sensitive data)

---

**Last Updated:** 2024-03-28

**Security Contact:** [GitHub Security Advisories](https://github.com/krittaphato3/MultiCode/security/advisories)
