/**
 * MultiCode 2.0 — tools.ts
 *
 * The built-in toolbelt. Everything routes through the sandbox from
 * safety.ts (fixes audit C2: no unvalidated paths anywhere).
 */

import { execFile } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import {
  analyzeCommand,
  resolveInSandbox,
  truncateOutput,
  type CommandAnalysis,
} from "./safety.js";
import type { Tool, ToolContext, ToolResult } from "./types.js";

const ok = (output: string): ToolResult => ({ ok: true, output });
const fail = (output: string): ToolResult => ({ ok: false, output });

// ---------------------------------------------------------------------------
// read_file
// ---------------------------------------------------------------------------

export const readFileTool: Tool = {
  name: "read_file",
  description:
    "Read a text file from the workspace. Returns full contents. " +
    "For binary or very large files, read with grep first to find line ranges.",
  schema: {
    name: "read_file",
    description: "Read a text file from the workspace",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "File path, relative to workspace root" },
      },
      required: ["path"],
    },
  },
  async execute(input, ctx): Promise<ToolResult> {
    try {
      const p = resolveInSandbox(ctx.baseDir, String(input.path ?? ""));
      const stat = await fs.stat(p);
      if (stat.size > 512 * 1024) {
        return fail(`File too large to read whole (${stat.size} bytes). Use grep to locate sections.`);
      }
      const content = await fs.readFile(p, "utf8");
      return ok(content);
    } catch (err) {
      return fail(err instanceof Error ? err.message : String(err));
    }
  },
};

// ---------------------------------------------------------------------------
// write_file
// ---------------------------------------------------------------------------

export const writeFileTool: Tool = {
  name: "write_file",
  description:
    "Create or overwrite a file. Parent directories are created automatically. " +
    "For edits to existing files prefer edit_file.",
  schema: {
    name: "write_file",
    description: "Create or overwrite a file with full contents",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "File path, relative to workspace root" },
        content: { type: "string", description: "Full file content to write" },
      },
      required: ["path", "content"],
    },
  },
  async execute(input, ctx): Promise<ToolResult> {
    try {
      const p = resolveInSandbox(ctx.baseDir, String(input.path ?? ""));
      await fs.mkdir(path.dirname(p), { recursive: true });
      // Atomic write: temp file + rename (audit M3: no partial writes).
      const tmp = `${p}.tmp-${process.pid}-${Date.now()}`;
      await fs.writeFile(tmp, String(input.content ?? ""), "utf8");
      await fs.rename(tmp, p);
      return ok(`Wrote ${path.relative(ctx.baseDir, p)} (${String(input.content ?? "").length} chars)`);
    } catch (err) {
      return fail(err instanceof Error ? err.message : String(err));
    }
  },
};

// ---------------------------------------------------------------------------
// edit_file (search/replace — replaces the Python regex approach, audit M3)
// ---------------------------------------------------------------------------

export const editFileTool: Tool = {
  name: "edit_file",
  description:
    "Replace an exact snippet in an existing file. The oldSnippet must match " +
    "the file exactly (use read_file first). Fails loudly if not found or ambiguous.",
  schema: {
    name: "edit_file",
    description: "Search-and-replace inside a file",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "File path, relative to workspace root" },
        oldSnippet: { type: "string", description: "Exact text to find" },
        newSnippet: { type: "string", description: "Replacement text" },
        replaceAll: { type: "boolean", description: "Replace every occurrence (default: first only)" },
      },
      required: ["path", "oldSnippet", "newSnippet"],
    },
  },
  async execute(input, ctx): Promise<ToolResult> {
    try {
      const p = resolveInSandbox(ctx.baseDir, String(input.path ?? ""));
      const content = await fs.readFile(p, "utf8");
      const oldS = String(input.oldSnippet ?? "");
      const newS = String(input.newSnippet ?? "");
      if (oldS === "") return fail("oldSnippet must not be empty");

      const first = content.indexOf(oldS);
      if (first === -1) {
        return fail(`oldSnippet not found in ${String(input.path)}. Read the file and retry with exact text.`);
      }
      const second = content.indexOf(oldS, first + 1);
      if (second !== -1 && input.replaceAll !== true) {
        return fail(
          `oldSnippet matches ${content.split(oldS).length - 1} times; provide more surrounding context or set replaceAll=true.`,
        );
      }
      const next = input.replaceAll === true
        ? content.split(oldS).join(newS)
        : content.slice(0, first) + newS + content.slice(first + oldS.length);

      if (next === content) return ok("No change (identical snippet).");
      const tmp = `${p}.tmp-${process.pid}-${Date.now()}`;
      await fs.writeFile(tmp, next, "utf8");
      await fs.rename(tmp, p);
      return ok(`Edited ${path.relative(ctx.baseDir, p)}`);
    } catch (err) {
      return fail(err instanceof Error ? err.message : String(err));
    }
  },
};

// ---------------------------------------------------------------------------
// grep (regex search with context)
// ---------------------------------------------------------------------------

export const grepTool: Tool = {
  name: "grep",
  description:
    "Regex search across workspace files. Skips node_modules/.git and binary files. " +
    "Returns file:line:match with optional context lines.",
  schema: {
    name: "grep",
    description: "Search file contents with a regex",
    parameters: {
      type: "object",
      properties: {
        pattern: { type: "string", description: "JavaScript-style regular expression" },
        glob: { type: "string", description: "Optional glob filter like *.ts (default: all text files)" },
        maxResults: { type: "number", description: "Max matches (default 50)" },
      },
      required: ["pattern"],
    },
  },
  async execute(input, ctx): Promise<ToolResult> {
    try {
      const pattern = String(input.pattern ?? "");
      const re = new RegExp(pattern, "i");
      const globFilter = input.glob ? globToRegExp(String(input.glob)) : null;
      const maxResults = Number(input.maxResults ?? 50);
      const results: string[] = [];
      const root = ctx.baseDir;

      await walk(root, async (filePath) => {
        if (results.length >= maxResults) return;
        if (globFilter && !globFilter.test(path.basename(filePath))) return;
        const stat = await fs.stat(filePath);
        if (stat.size > 1_000_000) return;
        const text = await fs.readFile(filePath, "utf8").catch(() => null);
        if (text === null) return;
        const lines = text.split("\n");
        for (let i = 0; i < lines.length && results.length < maxResults; i++) {
          if (re.test(lines[i] ?? "")) {
            results.push(`${path.relative(root, filePath)}:${i + 1}: ${(lines[i] ?? "").trim().slice(0, 200)}`);
          }
        }
      });

      return ok(results.length > 0 ? results.join("\n") : `No matches for /${pattern}/`);
    } catch (err) {
      return fail(`Bad regex or search error: ${err instanceof Error ? err.message : String(err)}`);
    }
  },
};

// ---------------------------------------------------------------------------
// glob (filename search)
// ---------------------------------------------------------------------------

export const globTool: Tool = {
  name: "glob",
  description: "Find files by name pattern, e.g. **/*.test.ts. Respects sandbox.",
  schema: {
    name: "glob",
    description: "List files matching a glob pattern",
    parameters: {
      type: "object",
      properties: {
        pattern: { type: "string", description: "Glob like src/**/*.ts" },
      },
      required: ["pattern"],
    },
  },
  async execute(input, ctx): Promise<ToolResult> {
    try {
      const pattern = String(input.pattern ?? "**/*");
      const re = globToRegExp(pattern);
      const matches: string[] = [];
      const root = ctx.baseDir;

      await walk(root, async (filePath) => {
        const rel = path.relative(root, filePath);
        if (re.test(rel.split(path.sep).join("/"))) {
          matches.push(rel.split(path.sep).join("/"));
        }
      });

      return ok(matches.slice(0, 200).join("\n") || "No files matched.");
    } catch (err) {
      return fail(err instanceof Error ? err.message : String(err));
    }
  },
};

// ---------------------------------------------------------------------------
// bash (sandboxed shell — safety.ts analysis + permission gate)
// ---------------------------------------------------------------------------

export const bashTool: Tool = {
  name: "bash",
  description:
    "Run a shell command in the workspace. Risky commands require user approval. " +
    "Output is truncated to keep context small.",
  schema: {
    name: "bash",
    description: "Execute a shell command in the workspace",
    parameters: {
      type: "object",
      properties: {
        command: { type: "string", description: "The command to run" },
        timeoutMs: { type: "number", description: "Timeout in ms (default 60000)" },
      },
      required: ["command"],
    },
  },
  async execute(input, ctx): Promise<ToolResult> {
    const command = String(input.command ?? "").trim();
    if (!command) return fail("Empty command");

    // (C1 fix) every segment of &&/;/| chains is analyzed.
    const analysis: CommandAnalysis = analyzeCommand(command);

    if (analysis.overall === "dangerous") {
      const granted = await ctx.requestPermission(
        `Dangerous command blocked: ${analysis.reasons.join("; ")}`,
        "high",
      );
      if (!granted) return fail(`DENIED by user: ${analysis.reasons.join("; ")}`);
    } else if (analysis.overall === "caution") {
      const granted = await ctx.requestPermission(
        `Command needs approval: ${analysis.reasons.join("; ")}`,
        "medium",
        );
      if (!granted) return fail(`DENIED by user: ${analysis.reasons.join("; ")}`);
    }

    const timeoutMs = Number(input.timeoutMs ?? 60_000);
    const shell = process.platform === "win32" ? "cmd.exe" : "/bin/sh";

    return new Promise((resolve) => {
      execFile(
        shell,
        process.platform === "win32" ? ["/c", command] : ["-c", command],
        { cwd: ctx.baseDir, timeout: timeoutMs, maxBuffer: 10 * 1024 * 1024, windowsHide: true },
        (err, stdout, stderr) => {
          const parts: string[] = [];
          if (stdout) parts.push(truncateOutput(stdout));
          if (stderr) parts.push(`[stderr]\n${truncateOutput(stderr)}`);
          if (err) {
            const code = "code" in err ? String((err as NodeJS.ErrnoException).code ?? err.message) : err.message;
            parts.push(`[exit ${code}]`);
            resolve(fail(parts.join("\n") || `Command failed: ${err.message}`));
          } else {
            resolve(ok(parts.join("\n") || "(no output)"));
          }
        },
      );
    });
  },
};

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

const IGNORED_DIRS = new Set([
  "node_modules", ".git", "dist", "build", "out", "coverage",
  ".venv", "venv", "__pycache__", ".next", ".turbo", ".cache",
]);

async function walk(root: string, visit: (filePath: string) => Promise<void>): Promise<void> {
  const queue: string[] = [root];
  while (queue.length > 0) {
    const dir = queue.pop() as string;
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (!IGNORED_DIRS.has(entry.name)) queue.push(full);
      } else if (entry.isFile()) {
        await visit(full);
      }
    }
  }
}

/** Minimal glob -> RegExp conversion (**, *, ?). */
export function globToRegExp(glob: string): RegExp {
  const escaped = glob
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*\*/g, "\u0000")
    .replace(/\*/g, "[^/]*")
    .replace(/\u0000/g, ".*")
    .replace(/\?/g, ".");
  return new RegExp(`^${escaped}$`);
}

export const defaultTools: Tool[] = [
  readFileTool,
  writeFileTool,
  editFileTool,
  grepTool,
  globTool,
  bashTool,
];
