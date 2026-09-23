# MultiCode — Architecture Audit & Roadmap

Status: v1.0.0 audit, September 2026.
Goal: turn MultiCode from a "multi-agent debate demo" into a top-tier agentic coding CLI with universal API connectivity and radical token efficiency.

---

## Part 1 — Current Architecture (as built)

```
main.py ─► ui/cli.py (2059-line god object)
              ├─ core/task_classifier.py   (heuristic only; AI classifier is dead code)
              ├─ simple ─► single OpenRouter call, regex file-write parse
              └─ complex ─► core/ultimate_multi_agent.py
                              ├─ _create_dynamic_team()   (LLM free-text → regex parse)
                              ├─ workflow steps           (agents discuss, re-send full context)
                              └─ final vote               ([CONSENSUS_REACHED] string match)
api/openrouter.py  — sync `requests` in thread pool, retry+backoff, dead model fallback chains
api/provider_manager.py + api/providers/* — parallel provider layer, NOT wired into the CLI
tools/filesystem.py — sandboxed file CRUD (full-content writes only)
tools/shell_tool.py — regex command blocklist, permission callback
core/agent_memory.py, snapshot.py, rollback.py, state_manager.py — infra, mostly unwired
```

**Verdict:** solid safety/audit scaffolding, but the agent core is "debate theater": many LLM round-trips for show, no real tool loop, no execution feedback, no incremental edits, no context management. Two API layers coexist; the better one (ProviderManager) is unused.

---

## Part 2 — Bugs & Flaws (found in audit)

### Critical (correctness / safety)

| # | Flaw | Where | Impact |
|---|------|-------|--------|
| C1 | **Chained-command bypass.** Safety regexes are anchored `^` on the first token: `echo hi && rm -rf /` classifies as *safe* (`echo`). No `&&`/`;`/`\|`/newline lexing. | `tools/shell_tool.py` `DANGEROUS_PATTERNS` | Full sandbox escape |
| C2 | **`working_dir` is unvalidated.** `ShellExecutionTool.execute(working_dir=...)` accepts any path; no sandbox check. | `tools/shell_tool.py:~486` | Sandbox escape |
| C3 | **`skip_safety_check=True`** is a caller-side parameter on the tool with no policy gate. | `tools/shell_tool.py:execute` | One flag disables all protection |
| C4 | **File-write regex false positives.** `FILE_WRITE_PATTERN` = ` ```(\w+)\s+([^\s`]+)\n(.*?)``` `. A plain explanatory block ` ```python\nprint("hi")\n``` ` parses as *path* `print("hi")` → agent writes garbage files from ordinary code snippets. | `core/agent.py:243` | Silent file corruption in user repos |
| C5 | **Dead model fallback chains.** `MODEL_FALLBACK_CHAIN` / `FREE_MODEL_FALLBACK_CHAIN` list stale/deprecated IDs (`claude-3.5-sonnet`, `gemini-pro-1.5`, `llama-3.1-405b`, etc.). Every fallback fails → compounding retries. | `api/openrouter.py:26-47` | Minutes of dead latency per failure |
| C6 | **Retry explosion.** HTTP-level retries (5, backoff to 300 s) × model-fallback chain (9 models) with no budget cap. Worst case hangs for hours; sync `time.sleep` inside executor. | `api/openrouter.py:_request_with_retry` | CLI freezes; no way to cancel cleanly |
| C7 | **Blocking I/O in async paths.** Pre-flight key check uses sync `requests.get` on the event loop (15 s timeout); `asyncio.get_event_loop()` (deprecated) in filesystem ops. | `ui/cli.py:~540`, `tools/filesystem.py` | UI freezes, 3.12+ warnings |
| C8 | **Headless mode is vaporware.** `--api` / `--task` / `--session` are parsed, stored… and never used. | `main.py:88-108`, `ui/cli.py:66-76` | Documented feature doesn't exist |

### Major (architecture)

| # | Flaw | Impact |
|---|------|--------|
| M1 | **No tool-calling.** The entire "agentic" surface is regex on fenced blocks. Agents are *told* "you can read files" but have no mechanism to issue reads/searches/shell — they code blind (top-level `iterdir()` only, no recursion, no .gitignore). | Cannot work in real codebases |
| M2 | **No execution feedback loop.** Nothing runs the code it writes; no tests, no linters, no error re-feed. This is the single biggest quality gap vs. Claude Code/Aider. | Low success rate on real tasks |
| M3 | **Full-content file writes only.** No diff/search-replace edits, no atomic writes, no rollback wiring (RollbackManager exists, unused). Large-file rewrite = token bomb + corruption risk. | Token waste + data loss risk |
| M4 | **Zero token management.** History grows unbounded; every workflow step re-sends user input + workflow + directory listing; debate mode re-sends everything × turns × agents. A stated goal ("Token Consumption Reduction") with zero implementation. | Cost scales with debate length |
| M5 | **ProviderManager is orphaned.** 8 provider types declared, 4 implemented (no Ollama/Groq/Mistral/Google classes), and the CLI hardcodes `OpenRouterClient` everywhere. "Connector to all APIs" is currently ~1.5 APIs. | The flagship goal is unimplemented |
| M6 | **Consensus-by-string-match.** Unanimous voting on `[CONSENSUS_REACHED]` text; up to 15 turns × N agents. Voting ≠ verification; tests/linters verify, votes don't. | Expensive, weak quality gate |
| M7 | **Fragile team parsing.** `AGENTS:`/`WORKFLOW:` free-text → regex (`task \| agent, agent`). Models drift off-format constantly. | Workflow generation unreliability |
| M8 | **Task routing.** AI classifier dead; heuristic matches substrings (`"and "`, `" with "`), English-only, defaults to *complex* → trivial tasks get the full debate. | Token waste, latency |
| M9 | **Packaging collision.** Installs top-level packages named `config`, `core`, `tools`, `api`, `ui`, `state` — generic names that can shadow/conflict with anything else on sys.path; `multicode/__init__.py` relies on a `sys.path` hack. README references files that no longer exist (`dynamic_orchestrator.py`, `collaborative_debate.py`, `events.py`, `state/memory.py`). | Breaks installs, docs mislead |
| M10 | **Audit not default.** README promises comprehensive audit logging; it's enabled only with `--audit-log` or `--mode audit`. | Security claim gap |
| M11 | **Test gaps.** 64 tests pass but cover only credentials/filesystem/redact/shell/state/classifier/uninstall. Nothing for agent parsing, orchestrator, providers, API client, CLI loop. | Core untested |

### Minor
- `main.py` double-imports `get_state_manager`; `ORIGINAL_CWD` captured in two modules inconsistently; `FileSystemTools` snapshots `Path.cwd()` at construction time.
- `_validate_encoding` silently rewrites unsupported encodings.
- Windows-first quirks (`readchar`, PowerShell paths) without CI matrix coverage.

---

## Part 3 — The Plan

### Phase 0 — Stabilize (1–2 weeks) — *make what exists actually safe & honest*
1. **Shell safety rewrite (C1–C3):** tokenize commands (shlex/PowerShell-aware), analyze *every* segment of `&&`/`;`/`|` chains; drop `skip_safety_check`; validate `working_dir` inside sandbox; ship with audit logging **on by default** (M10).
2. **File-write fix (C4):** only treat fenced blocks as writes when the path looks like a path (`/` or a known extension, no quotes/parens); otherwise render as normal markdown.
3. **API client hardening (C5–C7):** fetch live model list from `/models` and build fallback chains dynamically with a health cache; total-attempt budget + wall-clock deadline; `asyncio`-native client (aiohttp) with real SSE streaming; replace `time.sleep` with async backoff; non-blocking preflight.
4. **Finish headless mode (C8):** implement `--api --task "..."` → single JSON result on stdout (events on stderr). This unlocks CI usage and e2e testing of the whole engine.
5. **Truth pass:** README architecture section, drop "(Discontinue)", remove dead code (`classify_task` or wire it), fix double imports.

### Phase 1 — Real Agentic Engine (the core rewrite, 3–5 weeks)
6. **Native tool-calling layer.** Provider-agnostic tool schema → OpenAI `tools`, Anthropic `tool_use`, Gemini `functionDeclarations`; JSON-mode fallback (structured prompt + parse+repair) for providers without native calls. **Delete regex file writes.**
7. **Agent loop (ReAct).** One `AgentRunner`: model ↔ tools (`read_file`, `write_file`, `edit_file`, `grep`, `glob`, `bash`, `todo`) with iteration cap, token budget, and stop conditions. This replaces "debate" as the default engine.
8. **Diff-based edits.** Search/replace blocks (Aider-style) with fuzzy match + unified-diff fallback; atomic writes (temp + rename); wire the existing **RollbackManager** into every mutation; `/undo` command.
9. **Execution feedback.** Auto-run project test/lint commands after edits (detect via `pyproject.toml`/`package.json`/`Makefile`), feed failures back into the loop until green or budget out.
10. **Context engine.** ripgrep-backed search tool, .gitignore-aware repo map (tree-sitter tags), budgeted context assembly; per-agent context scoping.
11. **Token reduction (M4) — make it a feature, not a claim:**
    - prompt caching (Anthropic `cache_control`, OpenAI automatic) for system+repo-map prefixes;
    - rolling history compaction: summarize when nearing 70% of context window;
    - planner gets the repo map; workers get task-scoped slices only;
    - **replace N-way debate with a manager→worker orchestration by default**; "deliberate mode" (debate) becomes opt-in `/debate`;
    - live token + cost meter in the TUI.
12. **Structured outputs.** Team/workflow generation via JSON-schema tool calls (kills M7); routing via cheap heuristic → escalate to a 10-token model call only when ambiguous (revive `classify_task`).

### Phase 2 — Universal Provider Layer (2–3 weeks) — *"connector to all APIs"*
13. **One OpenAI-compatible core client** (base_url + key = new endpoint): OpenAI, OpenRouter, Groq, Mistral, Together, Fireworks, DeepSeek, xAI, Cerebras, Perplexity, LM Studio, **Ollama (`/v1`)**, vLLM, Azure OpenAI. Native adapters only where protocols differ: Anthropic, Google Gemini, AWS Bedrock, NVIDIA NIM (exists), Cohere.
14. **Make ProviderManager the single gateway** (kills M5): all agents/CLI requests flow through it; OpenRouter becomes *a* provider, not the backbone.
15. **Per-provider credentials** in OS keyring; model catalog cache with capability flags (tools / streaming / JSON / context length / pricing); **cross-provider fallback** (primary → same-tier → any configured provider); per-session cost tracking surfaced in the UI.
16. **MCP client (stdio + HTTP).** Any MCP server instantly becomes tools — GitHub, databases, browsers, etc. This is the real "all endpoints" multiplier and a top-tier differentiator.

### Phase 3 — Multi-Agent Done Right (2–3 weeks)
17. **Auto subagent spawning.** Orchestrator decomposes → spawns isolated subagents (own context, scoped tools, parallel via semaphore) → returns *summaries* to the orchestrator (Task-tool pattern). Token cost per subagent bounded by design.
18. **Verification over voting (M6).** Replace unanimous consensus with gates: tests green + linter clean + one reviewer agent. Debate stays available as opt-in.
19. **Checkpoints.** Snapshot/git auto-commit per completed step; resume any session (`--session` currently only names audit logs — make it real state).
20. **Role templates + memory.** Ship test-writer / refactorer / security-reviewer templates; feed `agent_memory` key-learnings into subagent prompts (store already exists).

### Phase 4 — Product Polish (ongoing)
21. **TUI:** real token streaming (Rich Live), markdown + syntax-highlighted diffs, plan-approval step, permission modes (ask / auto-edit / full-auto), `/undo`, `/cost`, `/models` per-task model override.
22. **Quality infra:** pytest coverage of the agent loop with a **mock provider** (no network in CI); CI matrix 3.10–3.13; e2e smoke via headless mode; track SWE-bench-lite + tokens-per-task as regressions dashboards.
23. **Packaging (M9):** single `src/multicode/` namespace (no `config`/`core`/`api` top-level names), no sys.path hacks; ship via pipx/uvx, winget/brew.

### Sequencing rationale
Phase 0 removes landmines. Phase 1 is the differentiator — tool loop + diff edits + test feedback is what separates real coding agents from chat wrappers. Phase 2 makes the provider story genuinely universal (cheap once tool-calling is abstracted, since one OpenAI-compatible client covers ~15 endpoints). Phase 3 rebuilds multi-agent on top of the loop instead of beside it.

### Definition of "top-tier"
- Solves multi-file tasks in real repos with test feedback and no regex-parsed writes.
- ≥15 endpoints connectable, cross-provider fallback, live cost meter.
- Token cost per task trending down release-over-release (tracked metric).
- Sandboxed by default, audited by default, undoable always.
