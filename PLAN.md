# MultiCode 2.0 — Rewrite Plan (TypeScript)

Language decision: **TypeScript on Node ≥20** (Bun optional for single-binary builds).
Migration mode: **stop-and-rewrite**. The Python tree in `../MultiCode` is frozen as a
reference; this repo is the continuation.

## Why TS (from the audit + language discussion)
- Proven stack for agentic CLIs (Claude Code, Gemini CLI, Amp). Biggest MCP + AI SDK ecosystem.
- Native `fetch`/streams/AbortController — the async primitives the Python version lacked (audit C6/C7).
- `npm i -g` distribution; optional `bun build --compile` single binary later.
- Zero runtime dependencies chosen deliberately: fewer supply-chain surfaces, and a tiny,
  readable codebase is the most accessible thing for a mixed/learning team.

## Status: scaffold complete (all green)

| Module | Replaces (Python) | Audit fixes baked in |
|---|---|---|
| `src/types.ts` | `api/providers/base.py` | One neutral message/tool/provider model for every adapter |
| `src/safety.ts` | `tools/shell_tool.py` | **C1** chained-command analysis, **C2** sandbox path validation, **C3** no bypass flag |
| `src/provider.ts` | `api/openrouter.py` + 4 provider classes | **C5** no stale hardcoded fallbacks, **C6** attempt budget + deadline + async backoff, **C7** fully async; one client covers ~15 OpenAI-compatible endpoints |
| `src/agent.ts` | `core/ultimate_multi_agent.py`, `core/agent.py` | Real ReAct loop (M1), token/turn/time budgets (M4), event stream (C8 groundwork) |
| `src/tools.ts` | `tools/filesystem.py` | Sandboxed read/write/edit/grep/glob/bash, atomic writes, **edit_file search-replace** (M3) |
| `src/index.ts` | `ui/cli.py`, `main.py` | Permission modes, **real headless `--json` mode** (C8), token/cost reporting, multi-provider flags, **AGENTS.md support** |
| `src/skills.ts` | — (new) | Agent Skills spec loader (agentskills.io): progressive disclosure, ~100-token eager cost per skill |
| `src/subagents.ts` | — (new, replaces debate theater) | Claude-Code-style Task tool: ephemeral isolated-context subagents (`spawn_agent`/`task`/`save_agent`), bounded summaries back to the orchestrator, session-end cleanup |

Tests: `tests/safety.test.ts`, `tests/tools.test.ts`, `tests/agent.test.ts`,
`tests/skills-subagents.test.ts` — 45 passing, offline (audit M11). Live
smoke-tested against the free keyless Pollinations provider (agentic file
reading, subagent delegation, skill activation, headless JSON).

## Next phases (port of the original ROADMAP)

1. **Finish the engine**
   - Streaming responses (SSE) end-to-end; token streaming in the TUI.
   - Repo map + prompt caching + rolling history compaction (token-reduction feature set, M4).
   - Auto test/lint detection (`package.json`, `pyproject.toml`, `Makefile`) and failure re-feed loop.
   - ~~Subagents~~ ✅ shipped: `spawn_agent`/`task`/`save_agent` with ephemeral registry and persistent templates.
   - Parallel subagent execution (Promise.all over independent tasks).
2. **Provider layer v2**
   - Keyring-backed per-provider credentials + `/auth` command.
   - Live model catalog per provider (capabilities: tools/streaming/json/context/pricing).
   - Cross-provider fallback with health memory. Native adapters only for Anthropic/Gemini/Bedrock.
3. **MCP client** (stdio + HTTP) — any MCP server becomes tools. The "all APIs and endpoints" multiplier.
4. **Product**
   - Rich TUI (plan-approval step, diffs, `/undo` via rollback transactions, `/cost`).
   - Checkpoints per completed step; session resume.
   - Ship: `npm i -g multicode`, then winget/brew via compiled binaries.

## Ground rules for contributors
- Keep runtime dependencies at zero; dev-only tooling is fine.
- No network in unit tests — mock providers/`fetchImpl` only.
- Every tool must route through `safety.ts`; no direct `child_process` outside `tools.ts`.
- New feature = tests first against the mock provider.
