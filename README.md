# MultiCode

![Demo](https://github.com/user-attachments/assets/49ee67c9-f054-4e7f-ab3b-fbc88cb88017)

**Agentic coding CLI** — reads, searches, edits, and runs commands in your
workspace until the task is done. Works with **any OpenAI-compatible endpoint**,
including fully **free, keyless providers**.

> v2 is a from-scratch TypeScript rewrite (see [PLAN.md](PLAN.md) and
> [docs/ROADMAP-audit.md](docs/ROADMAP-audit.md) for the architecture audit
> behind it). The previous Python implementation is preserved on the
> [`discontinued`](https://github.com/krittaphato3/MultiCode/tree/discontinued)
> branch.

```bash
# zero-config: free provider, no API key, no signup
npx tsx src/index.ts --provider pollinations "explain this repo"

# with your own key
export OPENAI_API_KEY=sk-...
npx tsx src/index.ts --provider openai "add retry with backoff to the poller"
```

---

## ✨ What it does

```
multicode "fix the failing tests in src/auth"
  ▸ glob       ✓   find test files
  ▸ read_file  ✓   read the failing module
  ▸ edit_file  ✓   patch the bug
  ▸ bash       ✓   run the test suite

Done · 9 turns · 12 tool calls · 18.4k tokens
```

- **Real agent loop** — the model uses tools (read / write / edit / grep /
  glob / bash) and iterates until done. No regex-parsed "file writes".
- **Multi-agent orchestration** — the model spawns ephemeral specialist
  subagents that work in their own context windows and report back summaries;
  persist the useful ones as reusable templates. See below.
- **Agent Skills (open spec)** — drop a `SKILL.md` folder in `skills/` and the
  agent picks it up, loading instructions only when relevant (progressive
  disclosure). Compatible with the [Agent Skills](https://agentskills.io)
  format; also reads `AGENTS.md` project instructions.
- **Budgeted by design** — max turns, token budget, wall-clock deadline,
  per-request timeout. The loop can't hang forever or silently retry.
- **Sandboxed by default** — every path stays inside the workspace, shell
  commands are analyzed **per segment** (`echo hi && rm -rf /` is caught), and
  risky actions need permission (`ask` / `auto-edit` / `yolo` modes).
- **One client, ~15 endpoints** — see providers below.
- **Headless JSON mode** — first-class `--json` output for CI and scripting.
- **Zero runtime dependencies** — ~1,400 lines of readable TypeScript.

## 🔌 Providers

| Provider | Endpoint | Key needed |
|---|---|---|
| `pollinations` | text.pollinations.ai — GPT-OSS 20B, tool-capable | **No — free** |
| `ollama` / `lm-studio` | localhost — your own local models | No |
| `openrouter` | 300+ models behind one key | Yes |
| `openai`, `groq`, `deepseek`, `together`, `fireworks`, `mistral`, `xai` | first-party APIs | Yes |
| `--base-url <url>` | any OpenAI-compatible server (vLLM, Azure proxies, …) | Varies |

Every provider goes through the same wire-protocol layer with bounded retries,
deadline budgets, and visible backoff (`[retry] HTTP 429 — retry 1/3 in 2s`).

## 🧩 Subagents — the token-saving team

The orchestrator doesn't have to do everything in its own context. It can
spawn **ephemeral specialist subagents** that work in isolated context
windows and return only bounded summaries:

```
spawn_agent { name: "test-runner", systemPrompt: "Run tests, summarize failures" }
task        { id: "test-runner-1", task: "make npm test pass" }
save_agent  { id: "test-runner-1" }   ← promote to a reusable template (optional)
```

```
 orchestrator (small context)          subagent (own isolated context)
┌──────────────────────────┐          ┌──────────────────────────────┐
│  plan + summaries only   │  task    │  reads, greps, runs commands │
│                          │ ◄────────│  burns tokens freely here    │
│  never sees the bulk     │  bounded │  (disposable)                │
│  of the work's tokens    │  summary │                              │
└──────────────────────────┘          └──────────────────────────────┘
```

- **Ephemeral by default** — subagents exist for the session, then are
  discarded automatically (with a token accounting line at exit).
- **`save_agent` promotes** proven specialists to `~/.multicode/agents/*.md`
  templates, injected into every future session's system prompt (one line
  each — progressive disclosure again).
- **Subagents never escalate privileges** — they inherit the orchestrator's
  permission policy, and they cannot spawn further subagents.

Live example (free keyless provider):

```
▸ spawn_agent … 🧩 spawned subagent reader (reader-1) — ephemeral
▸ task
  [reader#reader-1] ▸ glob → read_file → read_file   (its own context)
  ✓ task
Fruit: apple
Animal: zebra
🧹 1 ephemeral subagent(s) discarded · 2105 subagent tokens
── Done · 5 turns · 2 tool calls · 2662 tokens ──
```
The orchestrator used 2 tool calls and ~2.7k tokens total; the subagent's
~2.1k tokens of reading never entered the orchestrator's context.

## 🎯 Skills — teach MultiCode once, reuse forever

```xml
skills/
└── release-checklist/
    └── SKILL.md
```

```markdown
---
name: release-checklist
description: Run the release checklist. Use when the user says "release" or asks to cut a version.
---

1. Run `npm test`
2. Bump version in package.json
3. Update CHANGELOG.md
```

Only the name + one-line description load at startup (~100 tokens). The full
instructions load **only** when the agent activates the skill — and referenced
files load on demand from `references/` if the skill author provides them.
Format-compatible with the open [Agent Skills spec](https://agentskills.io).

## 🧭 Architecture

```
┌────────────────────────────────────────────────────────────┐
│                       src/index.ts (CLI)                   │
│  arg parsing · permission modes (ask/auto-edit/yolo)       │
│  --json headless mode · AGENTS.md · token/turn reporting   │
└───────────────┬────────────────────────────────────────────┘
                │ task + flags
┌───────────────▼────────────────────────────────────────────┐
│                     src/agent.ts (loop)                    │
│   ReAct loop: model ↔ tools until done                     │
│   budgets: maxTurns · tokenBudget · timeBudget             │
│   events: turn_start/assistant_text/tool_start/tool_end    │
┌───────────────┬─────────────────────────────┬──────────────┐
│               │                             │              │
┌───────────────▼──────────────┐  ┌───────────▼────────────┐ │
│      src/provider.ts         │  │      src/tools.ts      │ │
│ OpenAI-compatible client     │  │ read · write · edit    │ │
│ retries · deadline · usage   │  │ grep · glob · bash     │ │
└───────────────┬──────────────┘  └───────────┬────────────┘ │
│  ┌───────────────▼──────────────┐  ┌───────────▼────────────┐ │
│  │   src/subagents.ts           │  │     src/skills.ts      │ │
│  │  spawn_agent · task ·        │  │  SKILL.md discovery    │ │
│  │  save_agent · registry       │  │  progressive disclosure│ │
│  └───────────────┬──────────────┘  └────────────────────────┘ │
└──────────────────┼───────────────────────────────────────────┘
                   │
┌──────────────────▼─────────────────────────────────────────┐
│                      src/safety.ts                         │
│  path sandbox · per-segment command analysis · truncation  │
└────────────────────────────────────────────────────────────┘
```

### Request flow

```
 user task
    │
    ▼
 CLI (index.ts) ──► AgentRunner.run()
    │                     │
    │                     ▼
    │              provider.chat()          every turn:
    │                     │                 1. send messages + tool schemas
    │                     ▼                 2. model replies (text and/or tool_calls)
    │         POST /chat/completions        3. execute tool calls (sandboxed)
    │         (OpenRouter/OpenAI/Pollinations/  4. append tool results
    │          Ollama/… — any compatible)    5. repeat until no tool_calls
    │                                        or a budget trips
    │                     │
    │                     ▼
    │              tool execution ──► safety.ts (path check, command analysis,
    │                     │           permission gate) ──► fs / child_process
    ▼                     ▼
 result: finalText + usage + turns + toolCalls   (or JSON via --json)
```

## 🚀 Setup

```bash
npm install
npm run dev -- --provider pollinations "your task"     # free, no key
```

### CLI flags

| Flag | Meaning |
|---|---|
| `--provider <id>` | `pollinations` (free) · `openrouter` (default) · `openai` · `groq` · `deepseek` · `together` · `ollama` · … |
| `--model <id>` | model id (sensible default per provider) |
| `--api-key`, `--base-url` | custom credentials / any OpenAI-compatible endpoint |
| `--auto-edit` | approve file edits automatically, still ask before shell |
| `--yolo` | approve everything (CI only) |
| `--json` | headless JSON result on stdout (events → stderr) |
| `--max-turns <n>` | agent loop cap (default 25) |
| `--token-budget <n>` | token budget (default 500000) |
| `--timeout <ms>` | per-request timeout (default 120000) |

Env vars: `MULTICODE_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`,
`MULTICODE_PROVIDER`, `MULTICODE_MODEL`.

## 💻 Development

```bash
npm run typecheck   # strict TS, zero errors
npm test            # vitest — 45 tests, fully offline (mock providers)
npm run build       # emit dist/
```

Ground rules: zero runtime dependencies; no network in unit tests; every tool
routes through `safety.ts`; new features land with tests against the mock
provider first.

## 🗺️ Roadmap

Streaming output · repo map + prompt caching (more token reduction) ·
auto test/lint feedback loop · MCP client (any MCP server → tools) ·
checkpoints & `/undo` · published `npm i -g multicode`.

Details and phase-by-phase status: [PLAN.md](PLAN.md).

## 📄 License

MIT — see [LICENSE](LICENSE). (Carried over from the v1 project.)
