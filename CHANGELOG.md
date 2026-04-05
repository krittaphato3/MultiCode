# Changelog

All notable changes to MultiCode will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - Enterprise Release

### Security
- Credential fallback now uses XOR+base64 obfuscation with machine-derived key instead of plaintext
- Interpreter `-c` code execution (`python -c`, `node -c`, etc.) now requires user permission
- API key prefix removed from debug log output (was leaking first 4 chars)
- Structured secret redaction engine (`core/redact.py`) prevents keys, tokens, and PII in audit logs
- Pre-commit secrets scanner (`scripts/check-secrets.sh`) blocks accidental credential commits
- Comprehensive `.gitignore` covering audit logs, state files, and editor artifacts
- SECURITY_AUDIT.md with full security posture assessment

### Enterprise Features
- **Structured JSONL Audit Logging** (`core/audit.py`): Immutable audit trail with 17 event types, redacted details, pluggable sinks (file/stdout/webhook)
- **Enterprise CLI Flags**: `--mode=audit`, `--output=text|json|summary`, `--session=<name>`, `--api` (headless), `--audit-log=<path>`, `--task=<text>`
- **Agent Memory Management**: `/memory list`, `/memory show <agent>`, `/memory clear <agent>` commands for cross-session context
- **Enterprise Uninstall**: `/uninstall` (keep settings) and `/uninstall-wipe` (remove everything) with audit logging, cross-platform entry point cleanup, and post-uninstall validation
- **Intelligent Workflow Routing**: Automatic simple/complex task classification with `--mode` override
- **Configuration Template**: `config/enterprise.example.toml` with all settings documented
- **Makefile**: Common tasks — `make install`, `make lint`, `make test`, `make hooks`

### Repository Hygiene
- Version bumped to 1.0.0
- Moved `install.bat` and `cleanup.bat` to `scripts/`
- Merged `.ruff.toml` into `pyproject.toml` (single source of truth)
- Removed redundant `SUMMARY.md` and `PROJECT_STRUCTURE.md` (content in README/docs)
- Deleted root `__init__.py` and `-p/` artifact directory
- Added `Makefile` for cross-platform task automation

### Infrastructure
- `core/audit.py`: Structured JSONL audit logging with redaction
- `core/redact.py`: Pattern-based secret redaction (10 rules)
- `scripts/check-secrets.sh`: Pre-commit hook for secret detection
- `config/enterprise.example.toml`: Enterprise configuration template

### Fixed
- API key no longer appears in debug session headers log output
- Import sorting and type annotation modernization (`Optional[X]` → `X | None`, `List` → `list`, `Dict` → `dict`)
- Agent memory persistence wired into active workflow via `UltimateMultiAgentSystem`

## [Unreleased]

### Added
- **Structured Audit Logging**: Immutable JSONL audit trail with redacted events, pluggable sinks (file/stdout/webhook), tracking session lifecycle, agent actions, file ops, API calls, and voting outcomes
- **Secret Redaction Engine**: Pattern-based redaction of API keys, Bearer tokens, passwords, emails, IPs, and user paths in all log/audit output
- **Enterprise CLI Flags**: `--mode=audit`, `--output=text|json|summary`, `--session=<name>`, `--api` (headless mode), `--audit-log=<path>`, `--task=<text>`
- **Memory Management Commands**: `/memory list`, `/memory show <agent>`, `/memory clear <agent>` for cross-session agent context
- **Intelligent Workflow Routing**: Automatic detection of simple vs complex tasks — greetings and simple queries get instant single-agent responses, complex projects trigger full multi-agent debate
- **`--mode` CLI Flag**: Force workflow mode — `--mode simple` for always-direct, `--mode complex` for always-multi-agent, `--mode audit` for full audit trail
- **`/mode` Command**: Change routing mode interactively (`auto`, `simple`, `complex`)
- **Agent Memory Persistence**: Agents now remember conversation history and key learnings across sessions, enabling continuity between separate MultiCode runs
- **`--dry-run` Flag**: Preview file writes without executing them — see what files would be created/modified before committing
- **ASCII Banner Customization**: Choose from multiple banner themes (`default`, `minimal`, `fire`, `matrix`, `neon`) via the `/banner` command
- **Pre-Commit Secrets Scanner**: `scripts/check-secrets.sh` validates no secrets are committed
- **Security Audit Report**: `SECURITY_AUDIT.md` with comprehensive findings
- `routing` configuration section in settings with `enable_smart_routing` and `force_mode` options
- Audit mode (`audit`) added to `--mode` flag for compliance workflows

### Changed
- **Security Fix**: Removed full API key exposure from debug logs (was leaked via session headers dump)
- **Security Fix**: Reduced API key preview in debug logs from 12-char window to 4-char safe prefix
- Simple queries (greetings, math, single-file requests) now route to direct single-model response instead of full multi-agent — responses in 2-3 seconds
- `FileSystemTools.write_file()` now supports dry-run mode with operation preview logging
- `Agent` class accepts optional `memory_store` and `enable_persistent_memory` parameters
- `CollaborativeDebateLoop` saves agent memories after task completion

### Fixed
- Removed `__pycache__/` files from version control (were incorrectly tracked despite `.gitignore`)
- API key no longer appears in debug session headers log output
- Import sorting and type annotation modernization across codebase (`Optional[X]` → `X | None`, `List` → `list`, `Dict` → `dict`)

### Security
- File operations in dry-run mode are logged but never executed
- Credential fallback now uses XOR+base64 obfuscation instead of plaintext
- Interpreter `-c` code execution (`python -c`, `node -c`, etc.) now requires user permission
- API key prefix removed from debug log output (was leaking first 4 chars)
- Added `audit/`, `state/*.json`, `*.jsonl` to `.gitignore`
- Structured secret redaction engine prevents keys, tokens, and PII in audit logs

### Added
- Interactive model selector with presets (Coding, Free, Balanced, Quality)
- Cost estimator for selected models in model selection UI
- Visual cursor indicator ("► HERE") in model selector
- Selected model names display in status bar
- Search shortcuts (`free`, `coding`, `chat`, `speed`, `quality`)
- Quick preset selection with number keys (1-4)

### Changed
- **Model Selector**: Space key now toggles selection instead of adding to search
- **Model Selector**: Cursor initializes to first pre-selected model when using `/models`
- **Model Selector**: Navigation respects filtered list boundaries
- Improved visual clarity with separate cursor and selection indicators
- Updated help text to highlight Space key for toggling

### Fixed
- Model selector Space key conflict with search input
- Pre-selected models not properly initialized in model selector
- Cursor navigation not respecting filtered model list
- Dead code in `cli.py` (unreachable `console.print()` after return)
- ModelInfo class duplication (now uses `api.models.ModelInfo` directly)

### Security
- Enhanced shell command safety checks
- Improved path traversal prevention

## [0.2.0] - 2024-03-28

### Added
- Dynamic agent role generation
- Multi-agent debate system
- File CRUD operations with sandboxing
- Shell execution with safety checks
- Token management with auto-compression
- Event-driven architecture
- Dangerous command interceptor
- Path traversal prevention
- User confirmation for risky operations

### Changed
- Improved error handling throughout application
- Enhanced uninstall to remove all traces
- Updated README with security features

### Fixed
- Ctrl+C handling in all input prompts
- Arrow key selection display (no more duplicates)
- Working directory detection from any location
- Import errors in uninstall function

### Security
- Added secure credential storage with OS keyring integration
- Implemented command whitelist/blacklist for shell execution
- Added audit logging for all operations
- Restricted file operations to workspace directory

## [0.1.0] - 2024-03-27

### Added
- Initial release
- CLI interface with Rich
- OpenRouter API integration
- Model selection UI
- Basic configuration management

### Features
- Multi-agent architecture
- Secure API key storage
- Cross-platform support (Windows, macOS, Linux)

---

## Version History

| Version | Release Date | Status |
|---------|-------------|--------|
| [Unreleased] | - | In Development |
| [0.2.0] | 2024-03-28 | ✅ Current |
| [0.1.0] | 2024-03-27 | ⚠️ Legacy |

---

## Migration Guide

### Migrating from 0.1.x to 0.2.x

**Breaking Changes:**
- Configuration file moved from `config.json` to `settings.json`
- API key now stored in OS keyring by default

**Steps:**
1. Backup your configuration: `cp ~/.multicode/config.json ~/.multicode/config.json.bak`
2. Run MultiCode: it will automatically migrate your settings
3. Re-enter your API key if prompted

### Migrating from 0.2.x to Unreleased

**No breaking changes.** All improvements are backward compatible.

---

## Release Notes

### Unreleased (Model Selector Improvements)

This release focuses on improving the model selection experience:

**Key Improvements:**
1. **Fixed Space Key Behavior**: Space now toggles model selection instead of adding to search
2. **Better Visual Feedback**: Clear separation between cursor position and selection status
3. **Preset Support**: Quick-select presets for common use cases (Coding, Free, etc.)
4. **Cost Estimation**: See estimated costs before confirming model selection

**Bug Fixes:**
- Fixed issue where pre-selected models weren't properly initialized
- Fixed cursor navigation not respecting filtered lists
- Fixed ModelInfo class duplication

**How to Update:**
```bash
git pull origin main
pip install -e . --upgrade
```

---

[Unreleased]: https://github.com/krittaphato3/MultiCode/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/krittaphato3/MultiCode/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/krittaphato3/MultiCode/releases/tag/v0.1.0
