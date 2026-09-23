import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  discoverSkills,
  loadSkillBody,
  parseSkillMd,
  renderSkillCatalog,
} from "../src/skills.js";
import {
  SubagentRegistry,
  buildSubagentTools,
  loadAgentTemplates,
  parseAgentTemplate,
  renderPersistentAgents,
  saveAgentTemplate,
} from "../src/subagents.js";
import type { ModelReply, Provider, Tool } from "../src/types.js";

// ---------------------------------------------------------------------------
// Skills
// ---------------------------------------------------------------------------

const VALID_SKILL = `---
name: pdf-export
description: Export reports to PDF. Use when the user asks for PDF reports.
allowed-tools: read_file write_file bash
---

# PDF export

1. Read the report with read_file.
2. Render with scripts/render.py.
`;

describe("parseSkillMd", () => {
  it("parses valid frontmatter", () => {
    const meta = parseSkillMd(VALID_SKILL, "/x/pdf-export");
    expect(meta?.name).toBe("pdf-export");
    expect(meta?.description).toContain("PDF");
    expect(meta?.allowedTools).toEqual(["read_file", "write_file", "bash"]);
  });

  it("rejects invalid names and dir mismatch", () => {
    expect(parseSkillMd(VALID_SKILL.replace("pdf-export", "PDF-Export"), "/x/PDF-Export")).toBeNull();
    expect(parseSkillMd(VALID_SKILL, "/x/other-dir")).toBeNull();
    expect(parseSkillMd("no frontmatter here", "/x/pdf-export")).toBeNull();
  });

  it("rejects over-long descriptions", () => {
    const long = VALID_SKILL.replace(
      "Export reports to PDF. Use when the user asks for PDF reports.",
      "x".repeat(1100),
    );
    expect(parseSkillMd(long, "/x/pdf-export")).toBeNull();
  });
});

describe("discoverSkills (progressive disclosure)", () => {
  let dir: string;

  beforeEach(async () => {
    dir = await mkdtemp(path.join(tmpdir(), "mc-skills-"));
  });
  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("finds skills in project dir and merges with workspace dir", async () => {
    await mkdir(path.join(dir, ".multicode", "skills", "skill-a"), { recursive: true });
    await writeFile(path.join(dir, ".multicode", "skills", "skill-a", "SKILL.md"), VALID_SKILL.replace("pdf-export", "skill-a"));
    await mkdir(path.join(dir, "skills", "skill-b"), { recursive: true });
    await writeFile(path.join(dir, "skills", "skill-b", "SKILL.md"), VALID_SKILL.replace("pdf-export", "skill-b"));

    const { skills, errors } = await discoverSkills(dir);
    expect(skills.map((s) => s.name).sort()).toEqual(["skill-a", "skill-b"]);
    expect(errors).toHaveLength(0);

    // Catalog exposes only name+description (token-cheap).
    const catalog = renderSkillCatalog(skills);
    expect(catalog).toContain("skill-a");
    expect(catalog).not.toContain("scripts/render.py"); // body NOT loaded eagerly
  });

  it("reports invalid skills without crashing", async () => {
    await mkdir(path.join(dir, "skills", "broken"), { recursive: true });
    await writeFile(path.join(dir, "skills", "broken", "SKILL.md"), "garbage");
    const { skills, errors } = await discoverSkills(dir);
    expect(skills).toHaveLength(0);
    expect(errors.length).toBeGreaterThan(0);
  });

  it("loadSkillBody returns the full markdown body", async () => {
    await mkdir(path.join(dir, "skills", "pdf-export"), { recursive: true });
    await writeFile(path.join(dir, "skills", "pdf-export", "SKILL.md"), VALID_SKILL);
    const { skills } = await discoverSkills(dir);
    const loaded = await loadSkillBody(skills[0]!);
    expect(loaded.body).toContain("# PDF export");
    expect(loaded.body).toContain("scripts/render.py");
  });
});

// ---------------------------------------------------------------------------
// Subagents
// ---------------------------------------------------------------------------

function scriptedProvider(replies: ModelReply[]): Provider {
  let i = 0;
  return {
    id: "mock",
    label: "Mock",
    async chat() {
      return replies[Math.min(i++, replies.length - 1)]!;
    },
  };
}

function textReply(text: string): ModelReply {
  return {
    content: text,
    toolCalls: [],
    usage: { inputTokens: 10, outputTokens: 5 },
    stopReason: "end_turn",
    model: "mock-model",
    latencyMs: 1,
  };
}

const echoTool: Tool = {
  name: "echo",
  description: "Echo",
  schema: {
    name: "echo",
    description: "Echo",
    parameters: { type: "object", properties: { text: { type: "string" } }, required: ["text"] },
  },
  async execute(input) {
    return { ok: true, output: `echo: ${String(input.text ?? "")}` };
  },
};

describe("SubagentRegistry", () => {
  it("spawns, lists, and cleans up at session end", () => {
    const reg = new SubagentRegistry();
    const a = reg.spawn({ name: "researcher", systemPrompt: "You research." });
    const b = reg.spawn({ name: "tester", systemPrompt: "You test." });
    expect(reg.get(a)?.spec.name).toBe("researcher");
    expect(reg.list()).toHaveLength(2);

    const { discarded } = reg.endSession();
    expect(discarded).toHaveLength(2);
    expect(reg.isEmpty).toBe(true);
    expect(reg.get(b)).toBeUndefined();
  });
});

describe("buildSubagentTools", () => {
  let dir: string;
  beforeEach(async () => {
    dir = await mkdtemp(path.join(tmpdir(), "mc-subagents-"));
  });
  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  const makeDeps = (overrides?: Partial<Parameters<typeof buildSubagentTools>[0]>) => ({
    provider: scriptedProvider([textReply("subagent result here")]),
    model: "mock-model",
    tools: [echoTool],
    buildPermission: () => async () => true,
    registry: new SubagentRegistry(),
    templateCwd: dir,
    ...overrides,
  });

  it("spawn -> task -> bounded summary returned", async () => {
    const deps = makeDeps();
    const [spawn, task] = buildSubagentTools(deps);

    const spawned = await spawn.execute(
      { name: "researcher", systemPrompt: "Find things." },
      { cwd: dir, baseDir: dir, requestPermission: async () => true },
    );
    expect(spawned.ok).toBe(true);
    const id = /id: (.+)\)/.exec(spawned.output)?.[1] ?? "";

    const done = await task.execute(
      { id, task: "find the thing" },
      { cwd: dir, baseDir: dir, requestPermission: async () => true },
    );
    expect(done.ok).toBe(true);
    expect(done.output).toContain("[researcher] finished");
    expect(done.output).toContain("subagent result here");
    expect(deps.registry.get(id)?.invocations).toBe(1);
    expect(deps.registry.get(id)?.totalTokens).toBe(15);
  });

  it("task with unknown id fails cleanly", async () => {
    const deps = makeDeps();
    const [, task] = buildSubagentTools(deps);
    const res = await task.execute(
      { id: "nope", task: "x" },
      { cwd: dir, baseDir: dir, requestPermission: async () => true },
    );
    expect(res.ok).toBe(false);
    expect(res.output).toContain("Unknown subagent");
  });

  it("save_agent persists template to disk and loadAgentTemplates round-trips", async () => {
    const deps = makeDeps();
    const [spawn, , save] = buildSubagentTools(deps);

    await spawn.execute(
      { name: "test-runner", systemPrompt: "Run tests and summarize failures." },
      { cwd: dir, baseDir: dir, requestPermission: async () => true },
    );
    const id = deps.registry.list()[0]!.id;
    const saved = await save.execute({ id }, { cwd: dir, baseDir: dir, requestPermission: async () => true });
    expect(saved.ok).toBe(true);

    const file = path.join(dir, ".multicode", "agents", "test-runner.md");
    const raw = await readFile(file, "utf8");
    expect(raw).toContain("name: test-runner");
    expect(raw).toContain("Run tests and summarize failures.");

    const templates = await loadAgentTemplates(dir);
    expect(templates).toHaveLength(1);
    expect(templates[0]?.name).toBe("test-runner");
    expect(templates[0]?.systemPrompt).toContain("Run tests");

    const rendered = renderPersistentAgents(templates);
    expect(rendered).toContain("Persistent subagents");
    expect(rendered).toContain("test-runner");
  });

  it("parseAgentTemplate rejects malformed files", () => {
    expect(parseAgentTemplate("no frontmatter", "f.md")).toBeNull();
  });
});
