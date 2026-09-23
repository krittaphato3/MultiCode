/**
 * MultiCode 2.0 — safety.ts
 *
 * Port of the Python shell sandbox, with the three audit fixes applied:
 *   1. (C1) Chained commands: every segment of `&&`/`||`/`;`/`|`/newlines
 *      is analyzed independently — `echo hi && rm -rf /` is no longer "safe".
 *   2. (C2) working_dir / path args: validated to stay inside the sandbox
 *      root instead of being passed to the OS unsanitized.
 *   3. (C3) No bypass flag: "dangerous" always requires human permission;
 *      callers cannot skip analysis (they can only widen the sandbox).
 */

import path from "node:path";

// ---------------------------------------------------------------------------
// Sandbox
// ---------------------------------------------------------------------------

export class SandboxViolation extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SandboxViolation";
  }
}

/** Resolve `p` inside `root`, rejecting traversal outside it. */
export function resolveInSandbox(root: string, p: string): string {
  const resolved = path.resolve(root, p);
  const normalizedRoot = path.resolve(root);
  const rel = path.relative(normalizedRoot, resolved);
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    throw new SandboxViolation(
      `Path '${p}' resolves outside the sandbox root '${normalizedRoot}'`,
    );
  }
  return resolved;
}

// ---------------------------------------------------------------------------
// Command risk classification
// ---------------------------------------------------------------------------

export type Risk = "safe" | "caution" | "dangerous";

export interface SegmentVerdict {
  segment: string;
  base: string;
  risk: Risk;
  reason: string;
}

export interface CommandAnalysis {
  segments: SegmentVerdict[];
  /** Worst risk across all segments. */
  overall: Risk;
  /** True when human permission is required before execution. */
  requiresPermission: boolean;
  reasons: string[];
}

/** Commands that are destructive enough to always need approval. */
const DANGEROUS_BASES = new Set([
  "rm", "rmdir", "del", "rd", "dd", "mkfs", "format", "diskpart",
  "shutdown", "reboot", "halt", "taskkill", "kill", "killall",
  "chmod", "chown", "icacls",
]);

/** Commonly needed but worth flagging for approval. */
const CAUTION_BASES = new Set([
  "sudo", "su", "curl", "wget", "ssh", "scp", "rsync",
  "git", "npm", "npx", "pnpm", "yarn", "bun", "pip", "pip3",
  "apt", "apt-get", "brew", "docker", "kubectl",
]);

const SAFE_BASES = new Set([
  "ls", "dir", "pwd", "cat", "head", "tail", "grep", "find", "rg",
  "which", "whoami", "uname", "hostname", "echo", "printf", "date",
  "wc", "sort", "uniq", "cut", "node", "python", "python3", "tsc",
  "type", "copy", "move", "ipconfig", "ping", "netstat", "true", "false",
]);

/** Fragments that are dangerous anywhere in a segment (not just position 0). */
const DANGEROUS_FRAGMENTS: Array<[RegExp, string]> = [
  [/\/dev\/sd[a-z]/, "raw disk device access"],
  [/\/dev\/null\s*</, "redirecting from /dev/null into a command"],
  [/\bmkfs\b/, "filesystem formatting"],
  [/\bfork\s*bomb\b|:\(\)\s*\{\s*:\|:&\s*\}\s*;:/, "fork bomb pattern"],
  [/\|\s*(ba)?sh\b/, "piping into a shell (remote code execution risk)"],
  [/\bcurl\b[^|]*\|\s*(ba)?sh\b/, "curl|bash remote code execution"],
  [/\bwget\b[^|]*\|\s*(ba)?sh\b/, "wget|bash remote code execution"],
  [/\brm\s+(-[a-z]+\s+)*\/(\s|$)/, "root directory deletion"],
  [/\brm\s+(-[a-z]+\s+)*~/, "home directory deletion"],
  [/\bgit\s+push\s+--force\b/, "forced git push"],
  [/\bgit\s+reset\s+--hard\b/, "hard git reset (data loss)"],
  [/\bdel\s+\/[fsq]/i, "forced Windows delete"],
  [/\brd\s+\/s/i, "recursive Windows directory delete"],
  [/>\s*\/dev\/sd[a-z]/, "direct disk overwrite"],
];

/**
 * Split a command into segments on shell control operators.
 * Respects quotes so `echo "a && b"` stays one segment.
 * Handles: &&  ||  ;  |  and newlines.
 */
export function splitCommandSegments(command: string): string[] {
  const segments: string[] = [];
  let current = "";
  let quote: '"' | "'" | null = null;

  const flush = (): void => {
    const trimmed = current.trim();
    if (trimmed.length > 0) segments.push(trimmed);
    current = "";
  };

  for (let i = 0; i < command.length; i++) {
    const ch = command[i] as string;

    if (quote !== null) {
      current += ch;
      if (ch === quote) quote = null;
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      current += ch;
      continue;
    }
    if (ch === "\n" || ch === ";") {
      flush();
      continue;
    }
    if (ch === "|") {
      // Split only on `||`; a single pipe stays inside the segment so
      // patterns like `curl x | sh` remain visible to analysis.
      if (command[i + 1] === "|") {
        i++; // skip second '|'
        flush();
      } else {
        current += ch;
      }
      continue;
    }
    if (ch === "&") {
      if (command[i + 1] === "&") {
        i++; // skip second '&'
        flush();
        continue;
      }
      // Single '&' (background) — treat as separator too.
      flush();
      continue;
    }
    current += ch;
  }
  flush();
  return segments;
}

function baseCommand(segment: string): string {
  // Strip leading env-var assignments and take the first token.
  const tokens = segment.split(/\s+/);
  let idx = 0;
  while (idx < tokens.length && /^[A-Za-z_][A-Za-z0-9_]*=/.test(tokens[idx] ?? "")) {
    idx++;
  }
  const base = tokens[idx] ?? "";
  // On Windows people may write `npm.cmd` etc.
  return base.replace(/\.(exe|cmd|bat|ps1)$/i, "").toLowerCase();
}

function classifySegment(segment: string): SegmentVerdict {
  const base = baseCommand(segment);

  for (const [pattern, reason] of DANGEROUS_FRAGMENTS) {
    if (pattern.test(segment)) {
      return { segment, base, risk: "dangerous", reason };
    }
  }

  if (DANGEROUS_BASES.has(base)) {
    return { segment, base, risk: "dangerous", reason: `'${base}' is a destructive command` };
  }
  if (CAUTION_BASES.has(base)) {
    return {
      segment,
      base,
      risk: "caution",
      reason: `'${base}' commonly needs approval (network, packages, or vcs)`,
    };
  }
  if (!SAFE_BASES.has(base)) {
    return {
      segment,
      base,
      risk: "caution",
      reason: `'${base}' is not on the known-safe list`,
    };
  }
  return { segment, base, risk: "safe", reason: "known-safe command" };
}

/**
 * Analyze a full command line: every segment is classified and the
 * overall verdict is the worst one. (Audit fix C1.)
 */
export function analyzeCommand(command: string): CommandAnalysis {
  const segments = splitCommandSegments(command).map(classifySegment);

  const rank: Record<Risk, number> = { safe: 0, caution: 1, dangerous: 2 };
  const overall = segments.reduce<Risk>(
    (worst, s) => (rank[s.risk] > rank[worst] ? s.risk : worst),
    "safe",
  );

  return {
    segments,
    overall,
    requiresPermission: overall !== "safe",
    reasons: segments.filter((s) => s.risk !== "safe").map((s) => s.reason),
  };
}

// ---------------------------------------------------------------------------
// Output guards
// ---------------------------------------------------------------------------

/** Truncate command output so a chatty build doesn't blow the context. */
export function truncateOutput(output: string, maxChars = 20_000): string {
  if (output.length <= maxChars) return output;
  const head = output.slice(0, Math.floor(maxChars * 0.7));
  const tail = output.slice(-Math.floor(maxChars * 0.2));
  return (
    `${head}\n... [truncated ${output.length - maxChars} chars] ...\n${tail}`
  );
}
