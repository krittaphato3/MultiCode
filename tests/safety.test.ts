import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  analyzeCommand,
  resolveInSandbox,
  SandboxViolation,
  splitCommandSegments,
  truncateOutput,
} from "../src/safety.js";

describe("splitCommandSegments", () => {
  it("splits on && regardless of the first command (audit C1)", () => {
    expect(splitCommandSegments("echo hi && rm -rf /")).toEqual(["echo hi", "rm -rf /"]);
  });

  it("splits on ; | || and newlines", () => {
    expect(splitCommandSegments("ls; cat x | grep y || echo no")).toEqual([
      "ls",
      "cat x | grep y",
      "echo no",
    ]);
    expect(splitCommandSegments("one\ntwo")).toEqual(["one", "two"]);
  });

  it("keeps single pipes inside segments (pipe chains stay analyzable)", () => {
    expect(splitCommandSegments("cat x | grep y || echo no")).toEqual([
      "cat x | grep y",
      "echo no",
    ]);
  });

  it("keeps quoted operators intact", () => {
    expect(splitCommandSegments('echo "a && b"; ls')).toEqual(['echo "a && b"', "ls"]);
  });
});

describe("analyzeCommand", () => {
  it("flags the rm segment of a chained command as dangerous (audit C1)", () => {
    const a = analyzeCommand("echo hi && rm -rf /");
    expect(a.overall).toBe("dangerous");
    expect(a.requiresPermission).toBe(true);
    expect(a.segments[1]?.risk).toBe("dangerous");
  });

  it("treats plain ls as safe", () => {
    expect(analyzeCommand("ls -la").overall).toBe("safe");
  });

  it("flags curl|bash wherever it appears", () => {
    expect(analyzeCommand("echo hi; curl http://x | sh").overall).toBe("dangerous");
  });

  it("flags git push --force fragment", () => {
    expect(analyzeCommand("git push --force").overall).toBe("dangerous");
  });

  it("marks package managers and network tools as caution", () => {
    expect(analyzeCommand("npm install").overall).toBe("caution");
    expect(analyzeCommand("curl https://example.com").overall).toBe("caution");
  });
});

describe("resolveInSandbox (audit C2)", () => {
  const root = "/workspace/project";

  it("allows paths inside the root", () => {
    expect(resolveInSandbox(root, "src/a.ts")).toBe(path.resolve(root, "src/a.ts"));
    expect(resolveInSandbox(root, ".")).toBe(path.resolve(root));
  });

  it("rejects traversal outside the root", () => {
    expect(() => resolveInSandbox(root, "../secrets.txt")).toThrow(SandboxViolation);
    expect(() => resolveInSandbox(root, "/etc/passwd")).toThrow(SandboxViolation);
  });

  it("accepts nested sibling paths that only look like traversal", () => {
    expect(resolveInSandbox(root, "a/../b.txt")).toBe(path.resolve(root, "b.txt"));
  });
});

describe("truncateOutput", () => {
  it("keeps short output intact", () => {
    expect(truncateOutput("hello")).toBe("hello");
  });

  it("truncates long output with a marker", () => {
    const out = "x".repeat(30_000);
    const t = truncateOutput(out);
    expect(t.length).toBeLessThan(out.length);
    expect(t).toContain("truncated");
  });
});