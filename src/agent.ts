/**
 * MultiCode 2.0 — agent.ts
 *
 * The ReAct agent loop: model ↔ tools until done.
 * Replaces the Python "debate theater" with a real execution loop:
 *   - model replies with tool calls -> CLI executes them -> results go back
 *   - iteration cap + token budget + wall-clock budget
 *   - every step emitted as events (TUI renders, headless mode logs JSON)
 */

import type {
  AgentEvent,
  AgentEventHandler,
  AgentResult,
  Message,
  Provider,
  Tool,
} from "./types.js";

export interface AgentRunOptions {
  provider: Provider;
  model: string;
  system?: string;
  tools: Tool[];
  /** Conversation so far (user task included). Mutated copy is returned? No — kept internal. */
  messages: Message[];
  /** Hard cap on model turns. */
  maxTurns?: number;
  /** Stop when cumulative tokens exceed this. */
  tokenBudget?: number;
  /** Stop when wall clock exceeds this. */
  timeBudgetMs?: number;
  /** Sandbox root for tools. */
  cwd: string;
  /** Ask the human before risky ops. */
  requestPermission?: (reason: string, risk: "low" | "medium" | "high") => Promise<boolean>;
  onEvent?: AgentEventHandler;
  temperature?: number;
  maxTokensPerTurn?: number;
}

const DEFAULT_MAX_TURNS = 25;
const DEFAULT_TOKEN_BUDGET = 500_000;

export class AgentRunner {
  private readonly emit: AgentEventHandler;

  constructor(private readonly onEvent: AgentEventHandler = () => {}) {
    this.emit = onEvent;
  }

  async run(opts: AgentRunOptions): Promise<AgentResult & { messages: Message[] }> {
    const maxTurns = opts.maxTurns ?? DEFAULT_MAX_TURNS;
    const tokenBudget = opts.tokenBudget ?? DEFAULT_TOKEN_BUDGET;
    const startedAt = Date.now();

    const permissionFn =
      opts.requestPermission ?? (async () => true);

    const messages: Message[] = [...opts.messages];
    const toolMap = new Map(opts.tools.map((t) => [t.name, t]));

    let totalUsage = { inputTokens: 0, outputTokens: 0 };
    let toolCallCount = 0;
    let finalText = "";
    let stoppedBecause: AgentResult["stoppedBecause"] = "done";

    for (let turn = 1; turn <= maxTurns; turn++) {
      // Budget checks BEFORE spending another turn.
      if (totalUsage.inputTokens + totalUsage.outputTokens > tokenBudget) {
        stoppedBecause = "budget";
        break;
      }
      if (opts.timeBudgetMs && Date.now() - startedAt > opts.timeBudgetMs) {
        stoppedBecause = "budget";
        break;
      }

      await this.emit({ type: "turn_start", turn });

      const reply = await opts.provider.chat({
        messages,
        model: opts.model,
        system: opts.system,
        tools: opts.tools.map((t) => t.schema),
        temperature: opts.temperature,
        maxTokens: opts.maxTokensPerTurn,
      });

      totalUsage.inputTokens += reply.usage.inputTokens;
      totalUsage.outputTokens += reply.usage.outputTokens;

      if (reply.content) {
        finalText = reply.content;
        await this.emit({ type: "assistant_text", turn, data: reply.content });
      }

      // No tool calls -> the model is done.
      if (reply.toolCalls.length === 0) {
        messages.push({ role: "assistant", content: reply.content });
        await this.emit({ type: "turn_end", turn });
        stoppedBecause = "done";
        break;
      }

      // Record the assistant's tool-call message.
      messages.push({
        role: "assistant",
        content: [
          ...(reply.content ? [{ type: "text" as const, text: reply.content }] : []),
          ...reply.toolCalls,
        ],
      });

      // Execute each tool call and append results.
      const resultBlocks = [];
      for (const call of reply.toolCalls) {
        await this.emit({
          type: "tool_start",
          turn,
          data: { name: call.name, input: call.input },
        });
        toolCallCount++;

        const tool = toolMap.get(call.name);
        let output: string;
        let ok: boolean;

        if (!tool) {
          ok = false;
          output = `Unknown tool: ${call.name}. Available: ${[...toolMap.keys()].join(", ")}`;
        } else {
          try {
            const result = await tool.execute(call.input, {
              cwd: opts.cwd,
              baseDir: opts.cwd,
              requestPermission: permissionFn,
            });
            output = result.output;
            ok = result.ok;
          } catch (err) {
            ok = false;
            output = `Tool error: ${err instanceof Error ? err.message : String(err)}`;
          }
        }

        await this.emit({
          type: "tool_end",
          turn,
          data: { name: call.name, ok, output: output.slice(0, 500) },
        });

        resultBlocks.push({
          type: "tool_result" as const,
          toolUseId: call.id,
          content: output,
          isError: !ok,
        });
      }

      messages.push({ role: "tool", content: resultBlocks });
      await this.emit({ type: "turn_end", turn });

      if (reply.stopReason === "max_tokens") {
        stoppedBecause = "max_tokens";
        break;
      }
    }

    if (stoppedBecause === "done" && finalText === "") {
      // Loop ran out without a final message.
      stoppedBecause = "max_turns";
    }

    return {
      finalText,
      turns: Math.min(maxTurns, Math.max(1, messages.length)),
      toolCalls: toolCallCount,
      usage: totalUsage,
      stoppedBecause,
      messages,
    };
  }
}
