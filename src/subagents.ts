/**
 * MultiCode 2.0 — subagents.ts
 *
 * Subagent delegation, inspired by Claude Code's Task tool pattern, with the
 * MultiCode token-efficiency twist:
 *
 *   - Each subagent runs its own AgentRunner with an ISOLATED message list
 *     (its own context window). The orchestrator only receives a bounded
 *     result summary — never the subagent's full transcript. This keeps the
 *     orchestrator's context small (the #1 context saver).
 *   - Subagents are EPHEMERAL by default: they live for the session, and
 *     when the session ends they vanish. They can be PROMOTED to a reusable
 *     template with save_agent, stored under ~/.multicode/agents/<name>.md
 *     (Agent-Skills-style frontmatter so users can inspect/edit them).
 *   - The model can also AUTHOR new agents at runtime (create_agent) and
 *     either use them immediately (ephemeral) or persist them.
 */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { AgentRunner } from "./agent.js";
import type {
  AgentResult,
  Message,
  Provider,
  Tool,
  ToolContext,
  ToolResult,
} from "./types.ts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SubagentSpec {
  /** Unique per session (provided by the orchestrator or registry). */
  id: string;
  name: string;
  /** Role/system prompt: what this agent is an expert in. */
  systemPrompt: string;
  /** Tool names the subagent may use (defaults to all provided tools). */
  allowedTools?: string[];
  /** Per-subagent budgets — subagents MUST be cheaper than the main loop. */
  maxTurns?: number;
  maxTokensPerTurn?: number;
  /** Optional model override (e.g. a cheaper model for grunt work). */
  model?: string;
  temperature?: number;
  /** true once persisted to ~/.multicode/agents/<name>.md */
  persistent?: boolean;
}

interface SessionState {
  id: string;
  spec: SubagentSpec;
  /** Messages so far, so a named agent can be re-invoked with memory. */
  messages: Message[];
  invocations: number;
  totalTokens: number;
  lastResult?: AgentResult;
}

export interface SubagentSessionReport {
  agents: Array<{
    id: string;
    name: string;
    invocations: number;
    totalTokens: number;
    persistent: boolean;
  }>;
  totalTokens: number;
}

// ---------------------------------------------------------------------------
// Registry (per main-session)
// ---------------------------------------------------------------------------

export class SubagentRegistry {
  private readonly sessions = new Map<string, SessionState>();
  private counter = 0;

  /** Create a fresh ephemeral subagent. Returns its session id. */
  spawn(spec: Omit<SubagentSpec, "id" | "persistent">): string {
    this.counter++;
    const id = `${spec.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${this.counter}`;
    this.sessions.set(id, {
      id,
      spec: { ...spec, id, persistent: false },
      messages: [],
      invocations: 0,
      totalTokens: 0,
    });
    return id;
  }

  get(id: string): SessionState | undefined {
    return this.sessions.get(id);
  }

  list(): SessionState[] {
    return [...this.sessions.values()];
  }

  /** True when nothing is left (used by session-end cleanup reporting). */
  get isEmpty(): boolean {
    return this.sessions.size === 0;
  }

  /**
   * End-of-session cleanup. Ephemeral agents are discarded (returns their
   * ids); persistent ones survive in name only (their template is on disk).
   */
  endSession(): { discarded: string[] } {
    const discarded = this.list().map((s) => s.id);
    this.sessions.clear();
    return { discarded };
  }
}

// ---------------------------------------------------------------------------
// Persistence — ~/.multicode/agents/<name>.md (frontmatter + prompt body)
// ---------------------------------------------------------------------------

export function agentsDir(cwd?: string): string {
  return path.join(cwd ?? os.homedir(), ".multicode", "agents");
}

/** Home-based storage by default; tests pass an explicit cwd. */
export function agentTemplatePath(name: string, cwd?: string): string {
  const safe = name.toLowerCase().replace(/[^a-z0-9-]+/g, "-");
  return path.join(agentsDir(cwd), `${safe}.md`);
}

export async function saveAgentTemplate(
  spec: Omit<SubagentSpec, "id" | "persistent">,
  cwd?: string,
): Promise<string> {
  const file = agentTemplatePath(spec.name, cwd);
  await fs.mkdir(path.dirname(file), { recursive: true });
  const frontmatter = [
    "---",
    `name: ${spec.name.toLowerCase().replace(/[^a-z0-9-]+/g, "-")}`,
    `description: ${spec.systemPrompt.split("\n")[0]?.slice(0, 1024) || "Custom MultiCode subagent"}`,
    `tools: ${(spec.allowedTools ?? []).join(" ")}`,
    "persistent: true",
    "---",
    "",
    spec.systemPrompt,
    "",
  ].join("\n");
  await fs.writeFile(file, frontmatter, "utf8");
  return file;
}

export interface LoadedAgentTemplate {
  name: string;
  description: string;
  tools: string[];
  systemPrompt: string;
  file: string;
}

export async function loadAgentTemplates(cwd?: string): Promise<LoadedAgentTemplate[]> {
  const dir = agentsDir(cwd);
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  const out: LoadedAgentTemplate[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || !entry.name.endsWith(".md")) continue;
    // Directory-per-agent would be spec-style; we keep flat .md files here
    // because agent templates are a single prompt + metadata.
    continue;
  }
  // Flat files: ~/.multicode/agents/<name>.md
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
    const file = path.join(dir, entry.name);
    try {
      const raw = await fs.readFile(file, "utf8");
      const parsed = parseAgentTemplate(raw, file);
      if (parsed) out.push(parsed);
    } catch {
      // skip unreadable
    }
  }
  return out;
}

export function parseAgentTemplate(raw: string, file: string): LoadedAgentTemplate | null {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(raw);
  if (!m) return null;
  const fm = m[1] ?? "";
  const name = /^name:\s*(.+)\s*$/m.exec(fm)?.[1]?.trim() ?? "";
  const description = /^description:\s*(.+)\s*$/m.exec(fm)?.[1]?.trim() ?? "";
  const toolsRaw = /^tools:\s*(.*)$/m.exec(fm)?.[1]?.trim() ?? "";
  const body = (m[2] ?? "").trim();
  if (!name || !body) return null;
  return {
    name,
    description,
    tools: toolsRaw ? toolsRaw.split(/\s+/) : [],
    systemPrompt: body,
    file,
  };
}

// ---------------------------------------------------------------------------
// The tools exposed to the orchestrator
// ---------------------------------------------------------------------------

export interface SubagentToolDeps {
  provider: Provider;
  model: string;
  /** All tools the orchestrator has; subagents get a filtered subset. */
  tools: Tool[];
  /** Inherited permission policy — subagents never gain MORE rights. */
  buildPermission: (toolName: string) => ToolContext["requestPermission"];
  registry: SubagentRegistry;
  /** Warn/notify callback (CLI status line). */
  onEvent?: (msg: string) => void;
  /** Where persistent templates go (defaults to home). */
  templateCwd?: string;
  /** Hard cap on live subagents per session. */
  maxConcurrent?: number;
}

const BOUNDED_SUMMARY_LIMIT = 4000;

function boundedSummary(text: string): string {
  if (text.length <= BOUNDED_SUMMARY_LIMIT) return text;
  return `${text.slice(0, BOUNDED_SUMMARY_LIMIT)}\n... [output truncated — full result kept out of orchestrator context]`;
}

function filterTools(all: Tool[], allowed: string[] | undefined): Tool[] {
  if (!allowed || allowed.length === 0) return all;
  const set = new Set(allowed);
  return all.filter((t) => set.has(t.name));
}

/** Run one subagent session turn: isolated context, bounded return. */
async function runSubagent(
  state: SessionState,
  task: string,
  deps: SubagentToolDeps,
): Promise<ToolResult> {
  const spec = state.spec;
  const tools = filterTools(deps.tools, spec.allowedTools);
  const runner = new AgentRunner((event) => {
    if (event.type === "tool_start") {
      const d = event.data as { name: string };
      deps.onEvent?.(`[${spec.name}#${state.id}] ▸ ${d.name}`);
    }
  });

  const isFirstInvocation = state.invocations === 0;
  if (isFirstInvocation) {
    state.messages.push({ role: "user", content: task });
  } else {
    state.messages.push({ role: "user", content: `Follow-up: ${task}` });
  }

  const result = await runner.run({
    provider: deps.provider,
    model: spec.model ?? deps.model,
    system: spec.systemPrompt,
    tools,
    messages: state.messages,
    cwd: process.cwd(),
    maxTurns: spec.maxTurns ?? 10,
    maxTokensPerTurn: spec.maxTokensPerTurn ?? 2000,
    requestPermission: deps.buildPermission("subagent"),
  });

  state.invocations++;
  state.totalTokens += result.usage.inputTokens + result.usage.outputTokens;
  state.messages = result.messages;
  state.lastResult = result;

  const summary = [
    `[${spec.name}] finished in ${result.turns} turn(s), ${result.toolCalls} tool call(s), ${state.totalTokens} tokens total.`,
    result.stoppedBecause !== "done" ? `Note: stopped early (${result.stoppedBecause}).` : "",
    "",
    boundedSummary(result.finalText || "(no final text)"),
  ]
    .filter(Boolean)
    .join("\n");

  return { ok: result.stoppedBecause === "done", output: summary };
}

export function buildSubagentTools(deps: SubagentToolDeps): Tool[] {
  const maxConcurrent = deps.maxConcurrent ?? 6;

  const spawnTool: Tool = {
    name: "spawn_agent",
    description:
      "Create a temporary subagent for this session: a specialist with its own " +
      "context window, system prompt, and tool subset. Cheap and ephemeral — " +
      "use it to keep bulky research/reading out of your context. Give it a " +
      "crisp role like 'test-runner' or 'api-researcher'.",
    schema: {
      name: "spawn_agent",
      description: "Create an ephemeral specialist subagent",
      parameters: {
        type: "object",
        properties: {
          name: { type: "string", description: "Short kebab-case role name, e.g. test-runner" },
          systemPrompt: { type: "string", description: "The specialist's role and rules (1-3 sentences)" },
          allowedTools: {
            type: "array",
            items: { type: "string" },
            description: "Tool names it may use. Empty = all tools.",
          },
          model: { type: "string", description: "Optional model override (cheaper models for grunt work)" },
        },
        required: ["name", "systemPrompt"],
      },
    },
    async execute(input): Promise<ToolResult> {
      const name = String(input.name ?? "").trim();
      const systemPrompt = String(input.systemPrompt ?? "").trim();
      if (!name || !systemPrompt) return { ok: false, output: "name and systemPrompt are required" };
      if (deps.registry.list().length >= maxConcurrent) {
        return {
          ok: false,
          output: `Agent limit reached (${maxConcurrent} live). Reuse an existing agent with task, or let the session end.`,
        };
      }
      const id = deps.registry.spawn({
        name,
        systemPrompt,
        allowedTools: Array.isArray(input.allowedTools)
          ? (input.allowedTools as unknown[]).map(String)
          : undefined,
        model: input.model ? String(input.model) : undefined,
      });
      deps.onEvent?.(`🧩 spawned subagent ${name} (${id}) — ephemeral for this session`);
      return {
        ok: true,
        output: `Subagent '${name}' ready (id: ${id}). Give it work with the task tool.`,
      };
    },
  };

  const taskTool: Tool = {
    name: "task",
    description:
      "Delegate a task to a subagent by id. The subagent works in its own " +
      "context window and returns ONLY a bounded summary — your context stays " +
      "small. Re-invoking the same id continues that agent's conversation.",
    schema: {
      name: "task",
      description: "Delegate a task to a spawned subagent",
      parameters: {
        type: "object",
        properties: {
          id: { type: "string", description: "Subagent id from spawn_agent" },
          task: { type: "string", description: "What the subagent should do" },
        },
        required: ["id", "task"],
      },
    },
    async execute(input): Promise<ToolResult> {
      const id = String(input.id ?? "");
      const state = deps.registry.get(id);
      if (!state) {
        const known = deps.registry.list().map((s) => s.id).join(", ") || "none";
        return { ok: false, output: `Unknown subagent id '${id}'. Live agents: ${known}` };
      }
      const task = String(input.task ?? "").trim();
      if (!task) return { ok: false, output: "task is required" };
      return runSubagent(state, task, deps);
    },
  };

  const saveAgentTool: Tool = {
    name: "save_agent",
    description:
      "Promote a session subagent to a PERSISTENT reusable template, saved to " +
      "~/.multicode/agents/<name>.md. Persistent agents are available in all " +
      "future sessions. Use this when a specialist proved useful.",
    schema: {
      name: "save_agent",
      description: "Persist a subagent as a reusable template",
      parameters: {
        type: "object",
        properties: {
          id: { type: "string", description: "Subagent id from spawn_agent" },
        },
        required: ["id"],
      },
    },
    async execute(input): Promise<ToolResult> {
      const id = String(input.id ?? "");
      const state = deps.registry.get(id);
      if (!state) return { ok: false, output: `Unknown subagent id '${id}'` };
      const file = await saveAgentTemplate(
        {
          name: state.spec.name,
          systemPrompt: state.spec.systemPrompt,
          allowedTools: state.spec.allowedTools,
          model: state.spec.model,
        },
        deps.templateCwd,
      );
      state.spec.persistent = true;
      deps.onEvent?.(`💾 saved subagent '${state.spec.name}' → ${file}`);
      return {
        ok: true,
        output: `Saved '${state.spec.name}' as a persistent agent template at ${file}. It will be available in future sessions.`,
      };
    },
  };

  return [spawnTool, taskTool, saveAgentTool];
}

/**
 * Inject persistent agent templates into the system prompt (cheap: one line
 * each). The orchestrator can spawn a fresh instance of any of them by name.
 */
export function renderPersistentAgents(templates: LoadedAgentTemplate[]): string {
  if (templates.length === 0) return "";
  const lines = templates.map(
    (t) => `- ${t.name}: ${t.description || "(no description)"}${t.tools.length ? ` [tools: ${t.tools.join(",")}]` : ""}`,
  );
  return (
    `\n\n## Persistent subagents\n` +
    `Reusable specialists saved from previous sessions. To use one, spawn_agent ` +
    `with its exact name and copy its description as the systemPrompt seed:\n` +
    lines.join("\n")
  );
}
