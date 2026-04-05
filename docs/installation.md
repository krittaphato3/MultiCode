# Installation Guide

This guide provides detailed instructions for installing MultiCode on different platforms.

## 📋 Prerequisites

Before installing MultiCode, ensure you have:

- **Python 3.10 or higher** ([Download](https://www.python.org/downloads/))
- **pip** (Python package manager, included with Python)
- **OpenRouter API Key** ([Get Free](https://openrouter.ai/keys))
- **Git** (optional, for cloning the repository)

---

## 🔧 Installation Methods

### Method 1: Clone and Install (Recommended for Development)

This method is best if you want to contribute to MultiCode or modify the source code.

```bash
# Clone the repository
git clone https://github.com/krittaphato3/MultiCode.git
cd MultiCode

# Create a virtual environment (recommended)
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install as editable package
pip install -e .
```

**Verify Installation:**
```bash
multicode --version
```

---

### Method 2: Direct Installation (Recommended for Users)

This method is best if you just want to use MultiCode.

```bash
# Install from PyPI (when published)
pip install multicode
```

Or install directly from GitHub:

```bash
pip install git+https://github.com/krittaphato3/MultiCode.git
```

**Verify Installation:**
```bash
multicode --version
```

---

### Method 3: Manual Installation

If you prefer not to use pip:

```bash
# Clone or download the repository
git clone https://github.com/krittaphato3/MultiCode.git
cd MultiCode

# Install dependencies manually
pip install rich textual aiohttp keyring python-dotenv pydantic requests readchar
```

---

## 🖥️ Platform-Specific Instructions

### Windows

#### Step 1: Install Python

1. Download Python from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. ✅ **Important:** Check "Add Python to PATH" during installation

#### Step 2: Install MultiCode

```cmd
# Open Command Prompt or PowerShell
git clone https://github.com/krittaphato3/MultiCode.git
cd MultiCode

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install
pip install -r requirements.txt
pip install -e .
```

#### Troubleshooting Windows

**Error: "python" is not recognized**
```cmd
# Try python3 instead
python3 -m venv venv

# Or add Python to PATH manually
setx PATH "%PATH%;C:\Users\YourUsername\AppData\Local\Programs\Python\Python310"
```

**Error: Permission denied**
```cmd
# Run as Administrator or use:
pip install --user -r requirements.txt
```

---

### macOS

#### Step 1: Install Python

```bash
# Using Homebrew (recommended)
brew install python@3.10

# Or download from python.org
```

#### Step 2: Install MultiCode

```bash
git clone https://github.com/krittaphato3/MultiCode.git
cd MultiCode

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install
pip install -r requirements.txt
pip install -e .
```

#### Troubleshooting macOS

**Error: Command not found**
```bash
# Ensure Python is in PATH
export PATH="/usr/local/bin:$PATH"
```

**Error: Certificate verification failed**
```bash
# Install certificates
/Applications/Python\ 3.10/Install\ Certificates.command
```

---

### Linux

#### Step 1: Install Python

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip
```

**Fedora:**
```bash
sudo dnf install python3.10 python3-pip
```

**Arch Linux:**
```bash
sudo pacman -S python python-pip
```

#### Step 2: Install MultiCode

```bash
git clone https://github.com/krittaphato3/MultiCode.git
cd MultiCode

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install
pip install -r requirements.txt
pip install -e .
```

#### Troubleshooting Linux

**Error: No module named 'venv'**
```bash
# Install venv module
sudo apt install python3.10-venv  # Ubuntu/Debian
sudo dnf install python3.10-venv  # Fedora
```

---

## 🧪 Verify Installation

After installation, verify everything works:

```bash
# Check version
multicode --version

# Run MultiCode
multicode

# Or using Python directly
python main.py
```

---

## 🔑 First-Time Setup

When you run MultiCode for the first time:

1. **Enter API Key**: You'll be prompted for your OpenRouter API key
   - Get your key from [openrouter.ai/keys](https://openrouter.ai/keys)
   - The key is stored securely in your OS keyring

2. **Select Models**: Choose which AI models to use
   - Free models available (look for `:free` suffix)
   - Paid models offer higher quality

3. **Configure Agents**: Set the maximum number of agents
   - Recommended: 3-5 agents for most tasks
   - More agents = more thorough review but higher API costs

---

## 🔄 Updating MultiCode

### If Installed from Git

```bash
cd MultiCode
git pull origin main
pip install -e . --upgrade
```

### If Installed from PyPI

```bash
pip install multicode --upgrade
```

---

## 🗑️ Uninstallation

### Complete Uninstall

```bash
# Run the uninstall command from within MultiCode
multicode
/quit

# Then run
multicode --uninstall
# Or
python main.py --uninstall
```

### Manual Uninstall

```bash
# Uninstall package
pip uninstall multicode

# Remove configuration
rm -rf ~/.multicode  # Linux/Mac
rmdir /S %USERPROFILE%\.multicode  # Windows

# Remove cloned repository (if applicable)
rm -rf /path/to/MultiCode
```

---

## ❓ Common Issues

### "No module named 'rich'"

```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### "API key not found"

```bash
# Set API key as environment variable
export OPENROUTER_API_KEY="sk-or-..."  # Linux/Mac
set OPENROUTER_API_KEY="sk-or-..."  # Windows

# Or run setup again
multicode --reset
```

### "Permission denied" when installing

```bash
# Install to user directory
pip install --user -r requirements.txt
pip install --user -e .
```

### "Python version too old"

```bash
# Check Python version
python --version

# If < 3.10, install newer Python
# See platform-specific instructions above
```

---

## 📞 Getting Help

If you encounter issues:

1. **Check the [FAQ](faq.md)**
2. **Search [GitHub Issues](https://github.com/krittaphato3/MultiCode/issues)**
3. **Ask in [GitHub Discussions](https://github.com/krittaphato3/MultiCode/discussions)**
4. **Report a [new issue](https://github.com/krittaphato3/MultiCode/issues/new)**

---

<div align="center">

**Next:** [Quick Start Guide](quickstart.md)

[Back to Documentation](README.md)

</div>
