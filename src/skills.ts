/**
 * MultiCode 2.0 — skills.ts
 *
 * Agent Skills loader, compatible with the open Agent Skills specification
 * (agentskills.io). A skill is a directory containing SKILL.md:
 *
 *   skill-name/
 *     SKILL.md          required: YAML frontmatter + markdown body
 *     scripts/          optional
 *     references/       optional
 *
 * Progressive disclosure (the token-saving core):
 *   - At startup we load ONLY name + description (~100 tokens per skill)
 *     and expose those to the model as a catalog.
 *   - The full body is loaded ONLY when a skill is activated, via the
 *     `skill` tool or automatically by the agent loop.
 *   - referenced files load on demand via read_file.
 *
 * Skill sources (all optional, merged in this order):
 *   ~/.multicode/skills        user-level
 *   <cwd>/.multicode/skills    project-level
 *   <cwd>/skills               repo-style fallback
 */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

export interface SkillMeta {
  /** Spec: lowercase letters/numbers/hyphens, 1-64 chars, matches dir name. */
  name: string;
  /** Spec: 1-1024 chars; what it does + when to use it. */
  description: string;
  /** Optional experimental field: space-separated pre-approved tools. */
  allowedTools?: string[];
  /** Where the skill was found on disk. */
  dir: string;
  /** Where it was discovered. */
  source: "user" | "project" | "workspace";
}

export interface LoadedSkill extends SkillMeta {
  /** Full markdown body (instructions). */
  body: string;
}

const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

/** Parse SKILL.md content: YAML frontmatter + markdown body. */
export function parseSkillMd(raw: string, skillDir: string): SkillMeta | null {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(raw);
  if (!m) return null;

  const frontmatter = m[1] ?? "";
  const name = /^name:\s*(.+)\s*$/m.exec(frontmatter)?.[1]?.trim() ?? "";
  const description = /^description:\s*(.+)\s*$/m.exec(frontmatter)?.[1]?.trim() ?? "";
  const allowedToolsRaw = /^allowed-tools:\s*(.+)\s*$/m.exec(frontmatter)?.[1]?.trim() ?? "";

  if (!name || !description) return null;
  if (name.length > 64 || !NAME_RE.test(name)) return null;
  if (description.length > 1024) return null;
  if (path.basename(skillDir) !== name) return null;

  return {
    name,
    description,
    ...(allowedToolsRaw ? { allowedTools: allowedToolsRaw.split(/\s+/) } : {}),
    dir: skillDir,
    source: "workspace" as const,
  };
}

async function loadSkillsFromDir(
  dir: string,
  source: SkillMeta["source"],
  errors: string[],
): Promise<SkillMeta[]> {
  const found: SkillMeta[] = [];
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return found; // missing dir is fine
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const skillDir = path.join(dir, entry.name);
    try {
      const raw = await fs.readFile(path.join(skillDir, "SKILL.md"), "utf8");
      const meta = parseSkillMd(raw, skillDir);
      if (meta) {
        found.push({ ...meta, source });
      } else {
        errors.push(`${skillDir}: invalid SKILL.md (frontmatter, name rules, or dir/name mismatch)`);
      }
    } catch {
      errors.push(`${skillDir}: no readable SKILL.md`);
    }
  }
  return found;
}

export interface SkillCatalog {
  skills: SkillMeta[];
  /** Non-fatal discovery problems (surfaced in verbose mode). */
  errors: string[];
}

/** Discover skills from user + project + workspace locations. */
export async function discoverSkills(cwd: string): Promise<SkillCatalog> {
  const errors: string[] = [];
  const skills: SkillMeta[] = [];
  const seen = new Set<string>();

  const sources: Array<{ dir: string; source: SkillMeta["source"] }> = [
    { dir: path.join(os.homedir(), ".multicode", "skills"), source: "user" },
    { dir: path.join(cwd, ".multicode", "skills"), source: "project" },
    { dir: path.join(cwd, "skills"), source: "workspace" },
  ];

  // Later sources override earlier ones on name collision (project wins over
  // user, workspace over project) — same layering idea as AGENTS.md.
  const ordered: SkillMeta[] = [];
  for (const { dir, source } of sources) {
    for (const skill of await loadSkillsFromDir(dir, source, errors)) {
      if (seen.has(skill.name)) continue;
      seen.add(skill.name);
      ordered.push(skill);
    }
  }
  skills.push(...ordered);

  return { skills, errors };
}

/** Load the full body of a skill (activation step of progressive disclosure). */
export async function loadSkillBody(meta: SkillMeta): Promise<LoadedSkill> {
  const raw = await fs.readFile(path.join(meta.dir, "SKILL.md"), "utf8");
  const m = /^---\r?\n[\s\S]*?\r?\n---\r?\n?([\s\S]*)$/.exec(raw);
  return { ...meta, body: (m?.[1] ?? "").trim() };
}

/**
 * Compact catalog injected into the system prompt (~100 tokens per skill):
 * name + one-line description. This is the ONLY thing loaded eagerly.
 */
export function renderSkillCatalog(skills: SkillMeta[]): string {
  if (skills.length === 0) return "";
  const lines = skills.map((s) => `- ${s.name}: ${s.description}`);
  return (
    `\n\n## Available skills\n` +
    `Activate a skill with the skill tool (loads its full instructions):\n` +
    lines.join("\n")
  );
}
