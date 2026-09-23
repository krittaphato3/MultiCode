/**
 * MultiCode 2.0 — types.ts
 *
 * Core types for the provider-agnostic agent engine.
 * Ported conceptually from the Python audit (docs/ROADMAP.md): one shared
 * message/tool model that every provider adapter and the agent loop use.
 */

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------

export type Role = "system" | "user" | "assistant" | "tool";

/** Text block inside a message. */
export interface TextBlock {
  type: "text";
  text: string;
}

/** A tool invocation requested by the model. */
export interface ToolUseBlock {
  type: "tool_use";
  id: string;
  name: string;
  /** Arbitrary JSON arguments from the model. */
  input: Record<string, unknown>;
}

/** The CLI's result for a prior tool_use. */
export interface ToolResultBlock {
  type: "tool_result";
  /** Must match the originating tool_use id. */
  toolUseId: string;
  content: string;
  isError?: boolean;
}

export type ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock;

export interface Message {
  role: Role;
  content: string | ContentBlock[];
}

// ---------------------------------------------------------------------------
// Tools
// ---------------------------------------------------------------------------

/** JSON-schema-ish definition sent to the provider. */
export interface ToolSchema {
  name: string;
  description: string;
  parameters: {
    type: "object";
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export interface ToolContext {
  /** Sandbox root — every path op must resolve inside it. */
  cwd: string;
  /** Sandbox root for shell commands. */
  baseDir: string;
  /** Ask the human before a risky op; resolve true to allow. */
  requestPermission: (reason: string, risk: "low" | "medium" | "high") => Promise<boolean>;
}

export interface ToolResult {
  ok: boolean;
  output: string;
}

export interface Tool {
  name: string;
  description: string;
  schema: ToolSchema;
  execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult>;
}

// ---------------------------------------------------------------------------
// Provider responses
// ---------------------------------------------------------------------------

export interface Usage {
  inputTokens: number;
  outputTokens: number;
}

export interface StopReason {
  kind:
    | "end_turn"
    | "tool_use"
    | "max_tokens"
    | "stop_sequence"
    | "error";
  /** Populated when kind === "error". */
  message?: string;
}

export interface ModelReply {
  content: string;
  toolCalls: ToolUseBlock[];
  usage: Usage;
  stopReason: StopReason["kind"];
  /** Normalized model id, e.g. "anthropic/claude-sonnet-4.5". */
  model: string;
  /** Milliseconds the request took. */
  latencyMs: number;
}

// ---------------------------------------------------------------------------
// Agent loop
// ---------------------------------------------------------------------------

export interface AgentEvent {
  type:
    | "turn_start"
    | "assistant_text"
    | "tool_start"
    | "tool_end"
    | "turn_end"
    | "error";
  turn?: number;
  agent?: string;
  /** Optional payload depending on event type. */
  data?: unknown;
}

export type AgentEventHandler = (event: AgentEvent) => void | Promise<void>;

export interface AgentResult {
  finalText: string;
  turns: number;
  toolCalls: number;
  usage: Usage;
  stoppedBecause: "done" | "max_turns" | "max_tokens" | "budget" | "error";
  error?: string;
}

// ---------------------------------------------------------------------------
// Provider interface — the one every adapter implements
// ---------------------------------------------------------------------------

export interface Provider {
  readonly id: string;
  readonly label: string;
  chat(req: {
    messages: Message[];
    model: string;
    system?: string;
    tools?: ToolSchema[];
    temperature?: number;
    maxTokens?: number;
    signal?: AbortSignal;
  }): Promise<ModelReply>;
}

export class ProviderError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly retryAfterMs?: number,
  ) {
    super(message);
    this.name = "ProviderError";
  }
}
