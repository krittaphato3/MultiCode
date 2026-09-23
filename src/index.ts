/**
 * MultiCode 2.0 — index.ts
 *
 * CLI entry point. Supports:
 *   multicode "do the thing"          interactive with permission prompts
 *   multicode --auto-edit "task"      file edits auto-approved, shell still asks
 *   multicode --yolo "task"           everything auto-approved (CI)
 *   multicode --json "task"           headless: JSON result on stdout (audit C8)
 */

import fs from "node:fs/promises";
import path from "node:path";
import { stdin, stdout } from "node:process";
import readline from "node:readline/promises";
import { AgentRunner } from "./agent.js";
import { OpenAICompatProvider } from "./provider.js";
import { discoverSkills, loadSkillBody, renderSkillCatalog } from "./skills.js";
import {
  SubagentRegistry,
  buildSubagentTools,
  loadAgentTemplates,
  renderPersistentAgents,
} from "./subagents.js";
import { defaultTools } from "./tools.js";
import type { Tool } from "./types.js";

interface CliArgs {
  task: string;
  provider: string;
  model: string;
  apiKey?: string;
  baseUrl?: string;
  mode: "ask" | "auto-edit" | "yolo";
  json: boolean;
  maxTurns: number;
  tokenBudget: number;
  /** Per-request timeout; free endpoints can be slow, so make it tunable. */
  timeoutMs: number;
}

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {
    task: "",
    provider: process.env.MULTICODE_PROVIDER ?? "openrouter",
    model: process.env.MULTICODE_MODEL ?? "",
    apiKey:
      process.env.MULTICODE_API_KEY ??
      process.env.OPENROUTER_API_KEY ??
      process.env.OPENAI_API_KEY,
    baseUrl: process.env.MULTICODE_BASE_URL,
    mode: "ask",
    json: false,
    maxTurns: 25,
    tokenBudget: 500_000,
    timeoutMs: 120_000,
  };

  const positional: string[] = [];
  const argv1 = process.argv.slice(2);
  for (let i = 0; i < argv1.length; i++) {
    const a = argv1[i] as string;
    switch (a) {
      case "--provider": args.provider = String(argv1[++i] ?? ""); break;
      case "--model": args.model = String(argv1[++i] ?? ""); break;
      case "--api-key": args.apiKey = String(argv1[++i] ?? ""); break;
      case "--base-url": args.baseUrl = String(argv1[++i] ?? ""); break;
      case "--auto-edit": args.mode = "auto-edit"; break;
      case "--yolo": args.mode = "yolo"; args.json = false; break;
      case "--json": args.json = true; break;
      case "--max-turns": args.maxTurns = Number(argv1[++i] ?? 25); break;
      case "--token-budget": args.tokenBudget = Number(argv1[++i] ?? 500_000); break;
      case "--timeout": args.timeoutMs = Number(argv1[++i] ?? 120_000); break;
      case "--help":
      case "-h":
        printHelp();
        process.exit(0);
      default:
        positional.push(a);
    }
  }
  args.task = positional.join(" ");
  return args;
}

function printHelp(): void {
  console.log(`MultiCode 2.0 — agentic coding CLI

Usage:
  multicode [flags] "your task"

Flags:
  --provider <id>      openrouter | openai | groq | deepseek | pollinations (free, no key) | ollama | custom
  --model <id>         model id for the provider
  --api-key <key>      override MULTICODE_API_KEY env var
  --base-url <url>     custom OpenAI-compatible endpoint
  --auto-edit          auto-approve file edits, ask before shell
  --yolo               auto-approve everything (use in CI with care)
  --json               print JSON result instead of text (headless/CI)
  --max-turns <n>      agent loop cap (default 25)
  --token-budget <n>   token budget (default 500000)
  --timeout <ms>       per-request timeout (default 120000)

Env:
  MULTICODE_API_KEY    primary API key
  OPENROUTER_API_KEY   fallback for openrouter
  OPENAI_API_KEY       fallback for openai
  MULTICODE_PROVIDER   default provider id
  MULTICODE_MODEL      default model id
`);
}

const PROVIDER_BASE_URLS: Record<string, string> = {
  openrouter: "https://openrouter.ai/api/v1",
  openai: "https://api.openai.com/v1",
  groq: "https://api.groq.com/openai/v1",
  deepseek: "https://api.deepseek.com/v1",
  together: "https://api.together.xyz/v1",
  fireworks: "https://api.fireworks.ai/inference/v1",
  mistral: "https://api.mistral.ai/v1",
  xai: "https://api.x.ai/v1",
  ollama: "http://localhost:11434/v1",
  "lm-studio": "http://localhost:1234/v1",
  /** Free anonymous tier, no API key required (GPT-OSS 20B, tool-capable). */
  pollinations: "https://text.pollinations.ai/openai/v1",
};

/** Providers that work without any API key. */
const KEYLESS_PROVIDERS = new Set(["ollama", "lm-studio", "pollinations"]);

async function resolveEndpoint(
  args: CliArgs,
): Promise<{ baseUrl: string; apiKey?: string; model: string }> {
  const preset = PROVIDER_BASE_URLS[args.provider];
  const baseUrl = args.baseUrl ?? preset;
  if (!baseUrl) {
    throw new Error(
      `Unknown provider '${args.provider}'. Use --base-url for custom OpenAI-compatible endpoints.`,
    );
  }
  const apiKey = KEYLESS_PROVIDERS.has(args.provider) ? undefined : args.apiKey;
  const model = args.model || guessDefaultModel(args.provider);
  if (!model) {
    throw new Error(
      `No model specified. Pass --model or set MULTICODE_MODEL.`,
    );
  }
  return { baseUrl, apiKey, model };
}

function guessDefaultModel(provider: string): string {
  switch (provider) {
    case "openrouter": return "anthropic/claude-sonnet-4.5";
    case "openai": return "gpt-4.1";
    case "groq": return "llama-3.3-70b-versatile";
    case "deepseek": return "deepseek-chat";
    case "together": return "meta-llama/Llama-3.3-70B-Instruct-Turbo";
    case "xai": return "grok-4";
    case "ollama": return "qwen2.5-coder:7b";
    case "pollinations": return "openai-fast";
    default: return "";
  }
}

const SYSTEM_PROMPT = `You are MultiCode, an autonomous coding agent working in the user's workspace.

Rules:
- Inspect before you change: read files / grep before editing.
- Prefer edit_file with exact snippets over rewriting whole files.
- Verify: run tests/builds when they exist, then fix what fails.
- Keep responses short: status updates only, no filler.
- When the task is complete, summarize what changed in <=5 lines.

Delegation:
- For bulky research (reading many files, long output), spawn_agent a specialist
  and delegate with task instead of reading everything yourself — the specialist
  works in its own context and returns you only a summary. This keeps your
  context small and saves tokens.
- If a spawned agent proved broadly useful, persist it with save_agent.
- If the available-skills list has a skill matching the task, activate it with
  the skill tool before doing similar work manually.`;

async function askPermission(
  reason: string,
): Promise<boolean> {
  const rl = readline.createInterface({ input: stdin, output: stdout });
  try {
    const answer = (await rl.question(`\n⚠  ${reason}\n   Allow? [y/N/a(yolo)] `)).trim().toLowerCase();
    if (answer === "a") {
      console.log("[yolo mode enabled for this session]");
      return true;
    }
    return answer === "y" || answer === "yes";
  } finally {
    rl.close();
  }
}

async function main(): Promise<number> {
  const args = parseArgs(process.argv);
  if (!args.task) {
    printHelp();
    return 2;
  }

  const { baseUrl, apiKey, model } = await resolveEndpoint(args);

  // Load session context: AGENTS.md, skills (progressive disclosure),
  // and persistent subagent templates. Only metadata goes into the prompt.
  const agentsMd = await fs
    .readFile(path.join(process.cwd(), "AGENTS.md"), "utf8")
    .catch(() => null);
  const skillCatalog = await discoverSkills(process.cwd());
  const agentTemplates = await loadAgentTemplates();

  const provider = new OpenAICompatProvider({
    id: args.provider,
    label: args.provider,
    baseUrl,
    apiKey,
    timeoutMs: args.timeoutMs,
    onRetry: (msg) => {
      if (!args.json) console.error(`  [retry] ${msg}`);
    },
  });

  const permissionFor = (toolName: string) => {
    if (args.mode === "yolo") return async () => true;
    if (args.mode === "auto-edit") {
      return async (reason: string, risk: "low" | "medium" | "high") =>
        toolName === "bash" ? askPermission(reason) : true;
    }
    return async (reason: string, risk: "low" | "medium" | "high") => askPermission(reason);
  };

  // Wrap tools so permission policy is applied per tool name.
  const baseTools = defaultTools.map((tool) => ({
    ...tool,
    execute: async (input: Record<string, unknown>, ctx: Parameters<typeof tool.execute>[1]) => {
      const requestPermission = permissionFor(tool.name);
      return tool.execute(input, { ...ctx, requestPermission });
    },
  }));

  // Skill activation (progressive disclosure step 2: load the body on demand).
  const skillTool: Tool = {
    name: "skill",
    description:
      "Activate an available skill by name: loads its full instructions into " +
      "context. Use when the task matches a skill's description.",
    schema: {
      name: "skill",
      description: "Activate an available skill by name",
      parameters: {
        type: "object",
        properties: {
          name: { type: "string", description: "Skill name from the available skills list" },
        },
        required: ["name"],
      },
    },
    async execute(input) {
      const name = String(input.name ?? "");
      const meta = skillCatalog.skills.find((s) => s.name === name);
      if (!meta) {
        const known = skillCatalog.skills.map((s) => s.name).join(", ") || "none";
        return { ok: false, output: `Unknown skill '${name}'. Available: ${known}` };
      }
      const loaded = await loadSkillBody(meta);
      return {
        ok: true,
        output: `Skill '${name}' activated. Follow these instructions:\n\n${loaded.body}`,
      };
    },
  };

  // Subagent delegation: ephemeral specialists, savable as persistent templates.
  const registry = new SubagentRegistry();
  const subagentTools = buildSubagentTools({
    provider,
    model,
    tools: [...baseTools, skillTool], // no recursion: subagents cannot spawn subagents
    buildPermission: () => async () => true, // real gating lives in the wrapped tools
    registry,
    onEvent: (msg) => {
      if (!args.json) console.log(`  ${msg}`);
    },
  });

  const tools: Tool[] = [...baseTools, skillTool, ...subagentTools];

  const systemPrompt =
    SYSTEM_PROMPT +
    (agentsMd
      ? `\n\n## Project instructions (AGENTS.md)\n${agentsMd.slice(0, 8000)}`
      : "") +
    renderSkillCatalog(skillCatalog.skills) +
    renderPersistentAgents(agentTemplates);

  const runner = new AgentRunner((event) => {
    if (args.json) return; // headless: only final JSON
    switch (event.type) {
      case "tool_start":
        console.log(`\n▸ ${(event.data as { name: string }).name} ...`);
        break;
      case "tool_end": {
        const d = event.data as { name: string; ok: boolean; output: string };
        console.log(`  ${d.ok ? "✓" : "✗"} ${d.name}`);
        break;
      }
      case "assistant_text":
        console.log(`\n${(event.data as string).slice(0, 2000)}\n`);
        break;
      default:
        break;
    }
  });

  const result = await runner.run({
    provider,
    model,
    system: systemPrompt,
    tools,
    messages: [{ role: "user", content: args.task }],
    cwd: process.cwd(),
    maxTurns: args.maxTurns,
    tokenBudget: args.tokenBudget,
  });

  // Session teardown: ephemeral subagents are discarded by design.
  const agentStats = registry.list();
  const { discarded } = registry.endSession();
  if (!args.json && discarded.length > 0) {
    const subTokens = agentStats.reduce((sum, s) => sum + s.totalTokens, 0);
    console.log(
      `\n🧹 ${discarded.length} ephemeral subagent(s) discarded (session ended) · ${subTokens} subagent tokens`,
    );
  }

  if (args.json) {
    const payload = {
      ok: result.stoppedBecause === "done",
      stoppedBecause: result.stoppedBecause,
      result: result.finalText,
      turns: result.turns,
      toolCalls: result.toolCalls,
      usage: result.usage,
      model,
      provider: args.provider,
      ...(agentStats.length > 0
        ? {
            subagents: agentStats.map((s) => ({
              name: s.spec.name,
              invocations: s.invocations,
              tokens: s.totalTokens,
              persistent: s.spec.persistent === true,
            })),
          }
        : {}),
    };
    console.log(JSON.stringify(payload, null, 2));
  } else {
    const { usage } = result;
    console.log(
      `\n── ${result.stoppedBecause === "done" ? "Done" : `Stopped (${result.stoppedBecause})`}` +
      ` · ${result.turns} turns · ${result.toolCalls} tool calls` +
      ` · ${usage.inputTokens + usage.outputTokens} tokens ──`,
    );
  }

  return result.stoppedBecause === "done" ? 0 : 1;
}

main()
  .then((code) => process.exit(code))
  .catch((err: unknown) => {
    console.error(`multicode: ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
  });
