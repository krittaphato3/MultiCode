/**
 * MultiCode 2.0 — provider.ts
 *
 * The universal OpenAI-compatible chat-completions client with the audit
 * fixes applied:
 *   - (C5) No hardcoded stale model lists: fallback chains are supplied by
 *     the caller (from the live /models catalog), never hardcoded.
 *   - (C6) Bounded retries: attempt budget + wall-clock deadline, async
 *     backoff (no thread sleeps), respects `retryAfterMs` / Retry-After.
 *   - (C7) Fully async: native fetch + AbortSignal, no event-loop blocking.
 *
 * Any endpoint exposing POST {base}/chat/completions works: OpenRouter,
 * OpenAI, Groq, DeepSeek, Together, Fireworks, Mistral, xAI, Ollama (/v1),
 * LM Studio, vLLM, Cerebras, Perplexity...
 */

import type {
  Message,
  ModelReply,
  Provider,
  ToolSchema,
  Usage,
} from "./types.js";
import { ProviderError } from "./types.js";

export interface OpenAICompatOptions {
  id: string;
  label: string;
  baseUrl: string;
  apiKey?: string;
  /** Default model id if the caller passes an empty string. */
  defaultModel?: string;
  timeoutMs?: number;
  maxRetries?: number;
  /** Wall-clock budget for all retries of one logical request. */
  deadlineMs?: number;
  /** Optional observer for retry/backoff visibility (e.g. CLI stderr). */
  onRetry?: (message: string) => void;
  fetchImpl?: typeof fetch;
}

const DEFAULT_TIMEOUT_MS = 120_000;
const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_DEADLINE_MS = 180_000;

/** Convert our neutral Message format to OpenAI chat format. */
function toOpenAIMessages(
  messages: Message[],
  system?: string,
): Array<Record<string, unknown>> {
  const out: Array<Record<string, unknown>> = [];
  if (system) out.push({ role: "system", content: system });

  for (const msg of messages) {
    if (typeof msg.content === "string") {
      out.push({ role: msg.role, content: msg.content });
      continue;
    }
    // Structured content: tool calls from the assistant, results from tool role.
    const toolCalls = msg.content.filter((b) => b.type === "tool_use");
    const toolResults = msg.content.filter((b) => b.type === "tool_result");

    if (msg.role === "tool" || (toolResults.length > 0 && toolCalls.length === 0)) {
      for (const block of toolResults) {
        if (block.type !== "tool_result") continue;
        out.push({
          role: "tool",
          tool_call_id: block.toolUseId,
          content: block.content,
        });
      }
      continue;
    }

    if (toolCalls.length > 0) {
      out.push({
        role: "assistant",
        content: msg.content
          .filter((b) => b.type === "text")
          .map((b) => (b.type === "text" ? b.text : ""))
          .join(""),
        tool_calls: toolCalls.map((b) => {
          if (b.type !== "tool_use") return {};
          return {
            id: b.id,
            type: "function",
            function: { name: b.name, arguments: JSON.stringify(b.input) },
          };
        }),
      });
      continue;
    }

    // Fallback: join text blocks.
    out.push({
      role: msg.role,
      content: msg.content
        .filter((b) => b.type === "text")
        .map((b) => (b.type === "text" ? b.text : ""))
        .join(""),
    });
  }
  return out;
}

export class OpenAICompatProvider implements Provider {
  readonly id: string;
  readonly label: string;
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly defaultModel?: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly deadlineMs: number;
  private readonly onRetry?: (message: string) => void;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: OpenAICompatOptions) {
    this.id = opts.id;
    this.label = opts.label;
    this.baseUrl = opts.baseUrl.replace(/\/+$/, "");
    this.apiKey = opts.apiKey;
    this.defaultModel = opts.defaultModel;
    this.timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.maxRetries = opts.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.deadlineMs = opts.deadlineMs ?? DEFAULT_DEADLINE_MS;
    this.onRetry = opts.onRetry;
    this.fetchImpl = opts.fetchImpl ?? fetch;
  }

  /** POST {base}/chat/completions with bounded retries. */
  async chat(req: {
    messages: Message[];
    model: string;
    system?: string;
    tools?: ToolSchema[];
    temperature?: number;
    maxTokens?: number;
    signal?: AbortSignal;
  }): Promise<ModelReply> {
    const started = Date.now();
    const model = req.model || this.defaultModel || "";
    if (!model) throw new ProviderError("No model specified", 400);

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey) headers["Authorization"] = `Bearer ${this.apiKey}`;

    const body: Record<string, unknown> = {
      model,
      messages: toOpenAIMessages(req.messages, req.system),
      temperature: req.temperature ?? 0.7,
    };
    if (req.maxTokens) body.max_tokens = req.maxTokens;
    if (req.tools && req.tools.length > 0) {
      body.tools = req.tools.map((t) => ({
        type: "function",
        function: {
          name: t.name,
          description: t.description,
          parameters: t.parameters,
        },
      }));
    }

    const deadline = Date.now() + this.deadlineMs;
    let lastError: unknown;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      const timeoutCtrl = new AbortController();
      const onAbort = (): void => timeoutCtrl.abort();
      req.signal?.addEventListener("abort", onAbort, { once: true });
      const timer = setTimeout(() => timeoutCtrl.abort(), this.timeoutMs);
      try {
        const res = await this.fetchImpl(`${this.baseUrl}/chat/completions`, {
          method: "POST",
          headers,
          body: JSON.stringify(body),
          signal: timeoutCtrl.signal,
        });

        if (!res.ok) {
          const text = await res.text().catch(() => "");
          const err = new ProviderError(
            `HTTP ${res.status}: ${text.slice(0, 500)}`,
            res.status,
            parseRetryAfter(res.headers.get("retry-after")),
          );
          if (isRetryable(err) && Date.now() + backoffMs(attempt, err) < deadline) {
            lastError = err;
            this.onRetry?.(
              `HTTP ${res.status} — retry ${attempt + 1}/${this.maxRetries} in ${Math.round(backoffMs(attempt, err) / 1000)}s`,
            );
            await sleep(backoffMs(attempt, err), req.signal);
            continue;
          }
          throw err;
        }

        const data = (await res.json()) as {
          choices?: Array<{
            message?: {
              content?: string | null;
              tool_calls?: Array<{
                id: string;
                function: { name: string; arguments: string };
              }>;
            };
            finish_reason?: string;
          }>;
          usage?: { prompt_tokens?: number; completion_tokens?: number };
          model?: string;
        };

        const choice = data.choices?.[0];
        if (!choice) throw new ProviderError("Empty choices in response", 502);

        const toolCalls = (choice.message?.tool_calls ?? []).map((tc) => ({
          type: "tool_use" as const,
          id: tc.id,
          name: tc.function.name,
          input: safeJsonParse(tc.function.arguments),
        }));

        const usage: Usage = {
          inputTokens: data.usage?.prompt_tokens ?? 0,
          outputTokens: data.usage?.completion_tokens ?? 0,
        };

        return {
          content: choice.message?.content ?? "",
          toolCalls,
          usage,
          stopReason: mapFinish(choice.finish_reason, toolCalls.length > 0),
          model: data.model ?? model,
          latencyMs: Date.now() - started,
        };
      } catch (err) {
        if (req.signal?.aborted) {
          throw new ProviderError("Request aborted", 499);
        }
        // Network-level failure: retry within deadline.
        if (err instanceof ProviderError) throw err;
        lastError = err;
        if (attempt < this.maxRetries && Date.now() < deadline) {
          this.onRetry?.(`Network error (${String(err)}) — retry ${attempt + 1}/${this.maxRetries}`);
          await sleep(backoffMs(attempt), req.signal);
          continue;
        }
        throw new ProviderError(
          `Request failed after ${attempt + 1} attempt(s): ${String(err)}`,
        );
      } finally {
        clearTimeout(timer);
        req.signal?.removeEventListener("abort", onAbort);
      }
    }
    throw new ProviderError(
      `Retries exhausted: ${lastError instanceof Error ? lastError.message : String(lastError)}`,
    );
  }
}

function mapFinish(finish: string | undefined, hasToolCalls: boolean): ModelReply["stopReason"] {
  if (hasToolCalls) return "tool_use";
  switch (finish) {
    case "stop": return "end_turn";
    case "length": return "max_tokens";
    case "tool_calls": return "tool_use";
    case "content_filter": return "stop_sequence";
    default: return "end_turn";
  }
}

function safeJsonParse(s: string): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(s);
    return typeof parsed === "object" && parsed !== null
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

function isRetryable(err: ProviderError): boolean {
  const s = err.status ?? 0;
  return s === 429 || s >= 500;
}

function backoffMs(attempt: number, err?: ProviderError): number {
  if (err?.retryAfterMs) return err.retryAfterMs;
  return Math.min(1000 * 2 ** attempt, 30_000);
}

function parseRetryAfter(h: string | null): number | undefined {
  if (!h) return undefined;
  const s = Number(h);
  return Number.isFinite(s) ? Math.max(0, s * 1000) : undefined;
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        reject(new ProviderError("Request aborted", 499));
      },
      { once: true },
    );
  });
}
