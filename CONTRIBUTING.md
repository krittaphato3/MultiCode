# Contributing to MultiCode

Thank you for considering contributing to MultiCode! We welcome contributions from the community to help make MultiCode better.

<div align="center">

[Code of Conduct](CODE_OF_CONDUCT.md) • [Security Policy](SECURITY.md) • [License](LICENSE)

</div>

---

## 📋 Table of Contents

- [Code of Conduct](#-code-of-conduct)
- [Security First](#-security-first)
- [Getting Started](#-getting-started)
- [Development Setup](#-development-setup)
- [Code Standards](#-code-standards)
- [Testing](#-testing)
- [Documentation](#-documentation)
- [Pull Request Process](#-pull-request-process)
- [Commit Message Guidelines](#-commit-message-guidelines)
- [Code Review](#-code-review)
- [Questions?](#-questions)

---

## 🧭 Code of Conduct

Please read our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) to help make our community welcoming and safe. By participating, you are expected to uphold this code.

---

## 🔒 Security First

**IMPORTANT:** Do not report security vulnerabilities via public GitHub issues.

See [SECURITY.md](SECURITY.md) for proper reporting procedures.

---

## 🚀 Getting Started

### Find Something to Work On

Looking for inspiration? Check out:

- [Open Issues](https://github.com/krittaphato3/MultiCode/issues) - Bug reports and feature requests
- [Good First Issues](https://github.com/krittaphato3/MultiCode/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) - Perfect for newcomers
- [Help Wanted](https://github.com/krittaphato3/MultiCode/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) - Features we need help with

### Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/MultiCode.git
cd MultiCode

# Add the upstream repository
git remote add upstream https://github.com/krittaphato3/MultiCode.git
```

---

## 🛠️ Development Setup

### Prerequisites

- **Python 3.10+** ([Download](https://www.python.org/downloads/))
- **pip** (Python package manager)
- **Git** ([Download](https://git-scm.com/))

### Setup Development Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install development dependencies
pip install -e ".[dev]"

# Verify installation
pytest --version
ruff --version
black --version
```

### Configure Pre-commit Hooks (Optional)

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
```

---

## 📏 Code Standards

### Python Style Guide

We follow **PEP 8** with some modifications:

- **Line Length**: Maximum 100 characters
- **Indentation**: 4 spaces (no tabs)
- **Imports**: Grouped and sorted (handled by ruff)
- **Type Hints**: Required for all public functions
- **Docstrings**: Required for all public classes and functions

### Formatting

We use **Black** for code formatting:

```bash
# Format all code
black .

# Check formatting (CI)
black --check .
```

### Linting

We use **Ruff** for linting:

```bash
# Run linter
ruff check .

# Fix auto-fixable issues
ruff check . --fix

# Check specific file
ruff check path/to/file.py
```

### Type Checking

We use **Mypy** for type checking:

```bash
# Run type checker
mypy .

# Run on specific module
mypy multicode/core
```

---

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=multicode --cov-report=html

# Run specific test file
pytest tests/test_agent.py

# Run specific test function
pytest tests/test_agent.py::test_agent_creation

# Run tests matching a pattern
pytest -k "test_agent"
```

### Writing Tests

All new features and bug fixes require tests:

```python
# tests/test_example.py
import pytest
from multicode.core.agent import Agent

def test_agent_creation():
    """Test that an agent can be created."""
    agent = Agent(role_name="TestAgent", model_id="test-model")
    assert agent.role_name == "TestAgent"

@pytest.mark.asyncio
async def test_async_function():
    """Test async functions with pytest-asyncio."""
    result = await some_async_function()
    assert result is not None
```

### Test Coverage

We aim for **80%+ code coverage**:

```bash
# Check coverage
pytest --cov=multicode --cov-report=term-missing

# Coverage must not decrease for PRs to be accepted
```

---

## 📚 Documentation

### Code Comments

- Add docstrings to all public classes and functions
- Use Google-style docstrings:

```python
def calculate_total(items: list[float], tax_rate: float) -> float:
    """Calculate total cost including tax.

    Args:
        items: List of item prices
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)

    Returns:
        Total cost including tax

    Raises:
        ValueError: If tax_rate is negative
    """
    if tax_rate < 0:
        raise ValueError("Tax rate cannot be negative")

    subtotal = sum(items)
    return subtotal * (1 + tax_rate)
```

### Documentation Updates

Update documentation for user-facing changes:

- **README.md**: Update for new features or changes
- **docs/**: Add detailed documentation for complex features
- **CHANGELOG.md**: Document all changes (see below)

---

## 🔄 Pull Request Process

### Before Submitting

1. **Test your changes**
   ```bash
   pytest
   ruff check .
   black --check .
   mypy .
   ```

2. **Update documentation**
   - README.md for user-facing changes
   - Docstrings for code changes
   - CHANGELOG.md for all changes

3. **Ensure tests pass**
   ```bash
   pytest --cov=multicode
   ```

### Creating a PR

1. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Make your changes**

3. **Commit with clear messages** (see [Commit Message Guidelines](#-commit-message-guidelines))

4. **Push to your fork**
   ```bash
   git push origin feature/amazing-feature
   ```

5. **Open a Pull Request** on GitHub

### PR Template

When opening a PR, please fill out the template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have updated the documentation accordingly
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix/feature works
- [ ] All tests pass locally
- [ ] Coverage has not decreased
```

---

## 📝 Commit Message Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```bash
feat(agent): add dynamic agent role generation

Implemented AI-powered agent role creation based on task analysis.

Closes #123

---

fix(shell): prevent command injection vulnerability

Added input validation for shell commands.

Fixes #456

---

docs(readme): update installation instructions

Added detailed setup guide for Windows users.

---

test(agent): add unit tests for agent lifecycle

Added tests for agent creation, execution, and cleanup.
```

---

## 🔍 Code Review

All PRs require:

- **At least 1 approval** from a maintainer
- **All CI checks passing** (tests, linting, type checking)
- **No security concerns**
- **Documentation updated** (if applicable)

### Review Process

1. **Automated Checks**: CI runs tests, linting, and type checking
2. **Maintainer Review**: A maintainer reviews the code
3. **Feedback**: Address any feedback or requested changes
4. **Approval**: Once approved, PR is merged

---

## ❓ Questions?

- **General questions**: [GitHub Discussions](https://github.com/krittaphato3/MultiCode/discussions)
- **Bug reports**: [GitHub Issues](https://github.com/krittaphato3/MultiCode/issues)
- **Security issues**: See [SECURITY.md](SECURITY.md)
- **Code of Conduct violations**: Contact maintainers directly

---

## 🎉 Thank You!

Every contribution, no matter how small, helps make MultiCode better. We appreciate your time and effort!

<div align="center">

**Happy Coding! 🚀**

</div>
