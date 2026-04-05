# Quick Start Guide

Get up and running with MultiCode in 5 minutes!

## ⚡ 5-Minute Setup

### Step 1: Install (2 minutes)

```bash
# Clone and install
git clone https://github.com/krittaphato3/MultiCode.git
cd MultiCode
pip install -r requirements.txt
pip install -e .
```

### Step 2: Get API Key (1 minute)

1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Sign up or log in
3. Create a new API key
4. Copy the key (starts with `sk-or-`)

### Step 3: Run MultiCode (2 minutes)

```bash
multicode
```

On first run:
1. Paste your API key when prompted
2. Select models (press `2` for free models)
3. Set max agents (recommended: 3)

**Done!** You're ready to use MultiCode! 🎉

---

## 💬 Your First Task

Try a simple coding task:

```
multicode (): create a Python function that calculates fibonacci numbers
```

MultiCode will:
1. Analyze the task
2. Create appropriate agents
3. Generate and review code
4. Present the final solution

---

## 🎯 Example Tasks

### Simple Tasks (Instant Response)

```
multicode (): hello
multicode (): what is 15 * 23?
multicode (): explain what a decorator is in Python
```

### Coding Tasks (Multi-Agent)

```
multicode (): create a REST API with FastAPI
multicode (): write a script to scrape weather data
multicode (): build a todo list app with React
```

### Complex Projects

```
multicode (): create a full-stack blog with authentication
multicode (): build a data pipeline with Apache Airflow
multicode (): create a machine learning model for sentiment analysis
```

---

## 📋 Essential Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/models` | Change selected models |
| `/agents` | Change max agents |
| `/quit` | Exit MultiCode |

---

## 🎓 Learning Path

### Beginner

1. ✅ Complete the 5-minute setup above
2. ✅ Try simple tasks (greetings, math)
3. ✅ Create a small Python script
4. ✅ Experiment with different models

### Intermediate

1. Read [Configuration Guide](configuration.md)
2. Create multi-file projects
3. Use shell commands safely
4. Understand agent workflows

### Advanced

1. Read [Advanced Usage](usage/advanced.md)
2. Customize agent behavior
3. Create custom tools
4. Contribute to MultiCode!

---

## 💡 Tips for Best Results

### 1. Be Specific

❌ **Vague:** "make a website"
✅ **Specific:** "create a responsive landing page with HTML, CSS, and JavaScript"

### 2. Break Down Complex Tasks

❌ **Too Big:** "build an e-commerce site"
✅ **Better:** "create a product catalog page with search functionality"

### 3. Review Agent Output

- Agents show their reasoning
- Review code before running
- Ask for explanations if needed

### 4. Use the Right Models

- **Free models**: Good for learning and simple tasks
- **Paid models**: Better for complex projects and production code

---

## 🛡️ Safety Tips

1. **Review shell commands** before confirming
2. **Check file paths** before writing
3. **Test generated code** before using in production
4. **Keep API key secure** - never share it

---

## 📞 Need Help?

- **Stuck?** Check [Installation Guide](installation.md)
- **Questions?** Ask in [GitHub Discussions](https://github.com/krittaphato3/MultiCode/discussions)
- **Found a bug?** Report on [GitHub Issues](https://github.com/krittaphato3/MultiCode/issues)

---

## 🎉 Next Steps

Now that you're set up:

1. **Explore Features**: Read [Basic Usage](usage/basic.md)
2. **Learn Configuration**: See [Configuration Guide](configuration.md)
3. **Join Community**: Introduce yourself in [Discussions](https://github.com/krittaphato3/MultiCode/discussions)

---

<div align="center">

**Happy Coding! 🚀**

[Back to Documentation](README.md)

</div>
