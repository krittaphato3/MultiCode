# MultiCode

![b17fd556-788b-439d-9388-b669755d39c0](https://github.com/user-attachments/assets/49ee67c9-f054-4e7f-ab3b-fbc88cb88017)

<div align="center">

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg?style=for-the-badge)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge)](https://github.com/psf/black)
[![Security](https://img.shields.io/badge/security-audited-green.svg?style=for-the-badge)](SECURITY.md)

**Professional Multi-Agent AI Coding Assistant**

*Transform your coding workflow with AI-powered collaborative agents*

[Installation](#-quick-start) • [Features](#-features) • [Documentation](docs/) • [Security](SECURITY.md) • [Contributing](CONTRIBUTING.md)

</div>

---

## 🌟 Overview

MultiCode is an enterprise-grade, terminal-based AI coding assistant that leverages a **dynamic multi-agent debate system** to produce secure, high-quality code. Unlike single-model AI assistants, MultiCode creates custom teams of specialized AI agents that collaborate, debate, and review each other's work—mimicking real-world software development teams.

### Why MultiCode?

| Traditional AI Assistants | MultiCode |
|---------------------------|-----------|
| Single model opinion | **Multiple expert agents** |
| No code review | **Built-in peer review** |
| Generic responses | **Specialized expertise** |
| Trust but verify | **Unanimous consensus required** |

---

## ✨ Key Features

### 🤖 Dynamic Multi-Agent System

- **AI-Generated Roles**: Agents dynamically created based on your task (1-10+ agents)
- **Specialized Expertise**: Each agent has a custom role (Planner, Engineer, Security Reviewer, etc.)
- **Collaborative Workflow**: Agents debate and review each other's work
- **Unanimous Consensus**: All agents must agree before marking task complete

### 🛡️ Enterprise-Grade Safety

- **Dangerous Command Interceptor**: Blocks destructive commands automatically
- **Permission System**: User confirmation required for risky operations
- **File Sandboxing**: All file operations restricted to workspace directory
- **Audit Logging**: Comprehensive logging for compliance and debugging

### 💼 Professional Features

- **Secure Credential Storage**: API keys stored in OS keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- **Model Flexibility**: Access 300+ models via OpenRouter (free and paid options)
- **Cross-Platform**: Full support for Windows, macOS, and Linux
- **Extensible Architecture**: Plugin system for custom tools and agents

### 🎯 Intelligent Task Handling

- **Simple Query Detection**: Greetings and simple questions get instant responses
- **Complex Task Orchestration**: Multi-step projects trigger full agent workflow
- **Dynamic Workflow**: AI generates custom workflow steps based on task complexity
- **Fallback & Retry**: Automatic retry with error correction for failed steps

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** ([Download](https://www.python.org/downloads/))
- **OpenRouter API Key** ([Get Free](https://openrouter.ai/keys))
- **Git** (optional, for cloning)

### Installation

#### Option 1: Clone and Install (Recommended)

```bash
# Clone the repository
git clone https://github.com/krittaphato3/MultiCode.git
cd MultiCode

# Install dependencies
pip install -r requirements.txt

# Install as package (for global `multicode` command)
pip install -e .
```

#### Option 2: Direct Installation

```bash
pip install multicode
```

### First Run

```bash
# From anywhere (if installed with pip -e .)
multicode

# Or from project directory
python main.py
```

**On first run, MultiCode will:**
1. Prompt for your OpenRouter API key (stored securely in OS keyring)
2. Let you select AI models (free or paid)
3. Configure agent limits

---

## 📋 Usage Examples

### Simple Query (Instant Response)

```bash
multicode (): hello
💬 Response: Hello! How can I help you today?
```

### Math Question (Instant Response)

```bash
multicode (): what is 15 * 23?
💬 Response: 15 * 23 = 345
```

### Coding Task (Multi-Agent Workflow)

```bash
multicode (): create a Python calculator

📋 Workflow Steps
  Step 1: Plan calculator features
    → Agents: Planner
  Step 2: Implement add/subtract
    → Agents: Engineer
  Step 3: Implement multiply/divide
    → Agents: Engineer
  Step 4: Review code
    → Agents: Reviewer

✓ UNANIMOUS CONSENSUS REACHED
```

### Complex Project

```bash
multicode (): build a REST API with authentication

👥 AI-Created Team:
  • Architect - System design
  • BackendEngineer - API implementation
  • SecurityExpert - Authentication & authorization
  • Tester - Test coverage
  • Reviewer - Code quality

📋 Workflow:
  1. Design API architecture → Architect
  2. Implement endpoints → BackendEngineer
  3. Add authentication → SecurityExpert
  4. Write tests → Tester
  5. Final review → All agents

✓ PROJECT COMPLETE
```

---

## 🛡️ Security Features

| Feature | Description |
|---------|-------------|
| **API Key Storage** | OS keyring (Credential Manager/Keychain/Secret Service) |
| **Command Validation** | Whitelist + blocklist for shell commands |
| **File Sandboxing** | Operations restricted to workspace directory |
| **Audit Logging** | All operations logged with timestamps |
| **Permission System** | User confirmation for risky operations |
| **Rate Limiting** | Automatic backoff for API rate limits |

See [SECURITY.md](SECURITY.md) for detailed security information.

---

## ⚙️ Configuration

### Settings File

All settings stored in `~/.multicode/settings.json`:

```json
{
  "agent": {
    "max_agents": 3,
    "max_debate_turns": 15
  },
  "file_operations": {
    "allow_read": true,
    "allow_write": true,
    "allow_delete": false,
    "max_file_size_mb": 10
  },
  "api": {
    "timeout_seconds": 120,
    "default_model": "google/gemma-2-9b-it:free"
  },
  "safety": {
    "enable_shell_safety": true,
    "require_permission_for_sudo": true
  }
}
```

### Environment Variables

```bash
export OPENROUTER_API_KEY="sk-or-..."
export MULTICODE_MAX_AGENTS=5
export MULTICODE_MODEL="anthropic/claude-3.5-sonnet"
export MULTICODE_TIMEOUT=180
```

---

## 💬 Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/models` | Change selected models |
| `/agents` | Change max agents setting |
| `/pause` | Pause current AI task |
| `/continue` | Resume paused task |
| `/pwd` | Show working directory |
| `/uninstall` | Complete uninstall with confirmation |
| `/quit` | Exit MultiCode |

---

## 📊 Architecture

```
MultiCode/
├── main.py                      # Entry point
├── multicode/                   # Package for pip installation
├── config/
│   └── settings.py              # Centralized settings management
├── core/
│   ├── base_agent.py            # Abstract agent base class
│   ├── agent.py                 # Concrete agent implementation
│   ├── dynamic_orchestrator.py  # AI agent/workflow generation
│   ├── collaborative_debate.py  # Multi-agent debate loop
│   └── events.py                # Event bus (pub/sub)
├── tools/
│   ├── base_tool.py             # Abstract tool base
│   ├── filesystem.py            # File CRUD (sandboxed)
│   └── shell_tool.py            # Shell execution (sandboxed)
├── api/
│   ├── openrouter.py            # OpenRouter API client
│   └── models.py                # Model fetching & selection
├── ui/
│   └── cli.py                   # Rich CLI interface
└── state/
    └── memory.py                # Session state management
```

---

## 🧪 Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/krittaphato3/MultiCode.git
cd MultiCode

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=multicode --cov-report=html

# Run specific test file
pytest tests/test_agent.py
```

### Code Quality

```bash
# Run linter
ruff check .

# Format code
black .

# Type checking
mypy .
```

---

## 📈 Performance

| Task Type | Agents | Time | Example |
|-----------|--------|------|---------|
| Greeting | 0 (direct) | 2-5s | "hello" |
| Simple Math | 0 (direct) | 2-5s | "15*23=?" |
| Simple Code | 2-3 | 30-60s | "calculator" |
| Medium Project | 3-4 | 60-120s | "web scraper" |
| Complex App | 4-5 | 120-300s | "full-stack app" |

*Times may vary based on model selection and task complexity*

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Start for Contributors

```bash
# Fork the repository
# Clone your fork
git clone https://github.com/YOUR_USERNAME/MultiCode.git
cd MultiCode

# Create a feature branch
git checkout -b feature/amazing-feature

# Make your changes
# Run tests and linters
pytest
ruff check .

# Commit with conventional commits
git commit -m "feat: add amazing feature"

# Push and create PR
git push origin feature/amazing-feature
```

### Code of Conduct

Please read our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) to help make our community welcoming and safe.

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Built with [Rich](https://github.com/Textualize/rich) for beautiful terminal UI
- Powered by [OpenRouter](https://openrouter.ai) for multi-model access
- Security inspired by [Claude Code](https://claude.ai/code) and similar tools

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/krittaphato3/MultiCode/issues)
- **Discussions:** [GitHub Discussions](https://github.com/krittaphato3/MultiCode/discussions)
- **Security:** See [SECURITY.md](SECURITY.md)
- **Documentation:** [docs/](docs/)

---

<div align="center">

**Built with ❤️ and 🔒 by the MultiCode Team**

[![Star History Chart](https://api.star-history.com/svg?repos=krittaphato3/MultiCode&type=Date)](https://star-history.com/#krittaphato3/MultiCode&Date)

</div>
