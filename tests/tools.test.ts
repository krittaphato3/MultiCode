import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  editFileTool,
  globTool,
  grepTool,
  readFileTool,
  writeFileTool,
} from "../src/tools.js";
import type { ToolContext } from "../src/types.js";

let dir: string;

const ctx = (): ToolContext => ({
  cwd: dir,
  baseDir: dir,
  requestPermission: async () => true,
});

beforeEach(async () => {
  dir = await mkdtemp(path.join(tmpdir(), "multicode-test-"));
});

afterEach(async () => {
  await rm(dir, { recursive: true, force: true });
});

describe("read_file", () => {
  it("reads files inside the sandbox", async () => {
    await writeFile(path.join(dir, "a.txt"), "hello world");
    const res = await readFileTool.execute({ path: "a.txt" }, ctx());
    expect(res.ok).toBe(true);
    expect(res.output).toBe("hello world");
  });

  it("rejects traversal outside the sandbox (audit C2)", async () => {
    const res = await readFileTool.execute({ path: "../../etc/passwd" }, ctx());
    expect(res.ok).toBe(false);
    expect(res.output).toMatch(/outside the sandbox/i);
  });
});

describe("write_file", () => {
  it("creates nested files and reports size", async () => {
    const res = await writeFileTool.execute(
      { path: "src/nested/mod.ts", content: "export {};" },
      ctx(),
    );
    expect(res.ok).toBe(true);
    const read = await readFileTool.execute({ path: "src/nested/mod.ts" }, ctx());
    expect(read.output).toBe("export {};");
  });
});

describe("edit_file (replaces the Python regex approach, audit M3)", () => {
  it("replaces a unique snippet", async () => {
    await writeFile(path.join(dir, "app.py"), "def add(a, b):\n    return a + b\n");
    const res = await editFileTool.execute(
      {
        path: "app.py",
        oldSnippet: "return a + b",
        newSnippet: "return a + b  # typed",
      },
      ctx(),
    );
    expect(res.ok).toBe(true);
    const read = await readFileTool.execute({ path: "app.py" }, ctx());
    expect(read.output).toContain("# typed");
  });

  it("fails when the snippet is absent", async () => {
    await writeFile(path.join(dir, "x.txt"), "abc");
    const res = await editFileTool.execute(
      { path: "x.txt", oldSnippet: "zzz", newSnippet: "y" },
      ctx(),
    );
    expect(res.ok).toBe(false);
    expect(res.output).toMatch(/not found/i);
  });

  it("refuses ambiguous matches without replaceAll", async () => {
    await writeFile(path.join(dir, "y.txt"), "dup\ndup\n");
    const res = await editFileTool.execute(
      { path: "y.txt", oldSnippet: "dup", newSnippet: "x" },
      ctx(),
    );
    expect(res.ok).toBe(false);
    expect(res.output).toMatch(/2 times|replaceAll/i);
  });

  it("replaces all when replaceAll is set", async () => {
    await writeFile(path.join(dir, "z.txt"), "dup\ndup\n");
    const res = await editFileTool.execute(
      { path: "z.txt", oldSnippet: "dup", newSnippet: "x", replaceAll: true },
      ctx(),
    );
    expect(res.ok).toBe(true);
    const read = await readFileTool.execute({ path: "z.txt" }, ctx());
    expect(read.output).toBe("x\nx\n");
  });
});

describe("grep", () => {
  it("finds matches across files with line numbers", async () => {
    await writeFile(path.join(dir, "a.ts"), "const alpha = 1;\n");
    await writeFile(path.join(dir, "b.ts"), "const beta = alpha;\n");
    const res = await grepTool.execute({ pattern: "alpha" }, ctx());
    expect(res.ok).toBe(true);
    expect(res.output).toContain("a.ts:1:");
    expect(res.output).toContain("b.ts:1:");
  });

  it("reports no matches cleanly", async () => {
    const res = await grepTool.execute({ pattern: "nonexistent-xyz" }, ctx());
    expect(res.ok).toBe(true);
    expect(res.output).toMatch(/no matches/i);
  });
});

describe("glob", () => {
  it("matches nested patterns", async () => {
    await mkdir(path.join(dir, "src", "deep"), { recursive: true });
    await writeFile(path.join(dir, "src", "deep", "f.test.ts"), "test();");
    await writeFile(path.join(dir, "src", "plain.ts"), "const x = 1;");
    const res = await globTool.execute({ pattern: "**/*.test.ts" }, ctx());
    expect(res.ok).toBe(true);
    expect(res.output).toContain("src/deep/f.test.ts");
    expect(res.output).not.toContain("plain.ts");
  });
});
