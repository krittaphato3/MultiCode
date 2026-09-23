import { describe, expect, it } from "vitest";
import { AgentRunner } from "../src/agent.js";
import { OpenAICompatProvider } from "../src/provider.js";
import type { Message, ModelReply, Provider, Tool } from "../src/types.js";

// ---------------------------------------------------------------------------
// Mock provider: scripted replies, no network (audit M11: core must be
// testable offline).
// ---------------------------------------------------------------------------

function scriptedProvider(replies: ModelReply[]): Provider {
  let i = 0;
  return {
    id: "mock",
    label: "Mock",
    async chat() {
      const reply = replies[i] ?? replies[replies.length - 1]!;
      i++;
      return reply;
    },
  };
}

function textReply(text: string, stop = "end_turn"): ModelReply {
  return {
    content: text,
    toolCalls: [],
    usage: { inputTokens: 10, outputTokens: 5 },
    stopReason: stop,
    model: "mock-model",
    latencyMs: 1,
  };
}

function toolReply(calls: Array<{ id: string; name: string; input: Record<string, unknown> }>): ModelReply {
  return {
    content: "",
    toolCalls: calls.map((c) => ({ type: "tool_use" as const, ...c })),
    usage: { inputTokens: 10, outputTokens: 5 },
    stopReason: "tool_use",
    model: "mock-model",
    latencyMs: 1,
  };
}

const echoTool: Tool = {
  name: "echo",
  description: "Echo back the input",
  schema: {
    name: "echo",
    description: "Echo back the input",
    parameters: {
      type: "object",
      properties: { text: { type: "string" } },
      required: ["text"],
    },
  },
  async execute(input) {
    return { ok: true, output: `echo: ${String(input.text ?? "")}` };
  },
};

const boomTool: Tool = {
  ...echoTool,
  name: "boom",
  description: "Always throws",
  schema: { ...echoTool.schema, name: "boom", description: "Always throws" },
  async execute() {
    throw new Error("kaboom");
  },
};

// ---------------------------------------------------------------------------
// Agent loop tests
// ---------------------------------------------------------------------------

describe("AgentRunner", () => {
  it("returns the final text when the model stops without tools", async () => {
    const runner = new AgentRunner();
    const result = await runner.run({
      provider: scriptedProvider([textReply("all done")]),
      model: "mock-model",
      tools: [echoTool],
      messages: [{ role: "user", content: "hi" }],
      cwd: ".",
    });
    expect(result.finalText).toBe("all done");
    expect(result.stoppedBecause).toBe("done");
    expect(result.toolCalls).toBe(0);
    expect(result.usage.inputTokens).toBe(10);
  });

  it("executes tool calls and feeds results back until done", async () => {
    const runner = new AgentRunner();
    const result = await runner.run({
      provider: scriptedProvider([
        toolReply([{ id: "t1", name: "echo", input: { text: "hello" } }]),
        textReply("finished with tool output"),
      ]),
      model: "mock-model",
      tools: [echoTool],
      messages: [{ role: "user", content: "use the tool" }],
      cwd: ".",
    });
    expect(result.toolCalls).toBe(1);
    expect(result.stoppedBecause).toBe("done");
    expect(result.finalText).toBe("finished with tool output");

    const toolMsg = result.messages.find(
      (m) => m.role === "tool",
    ) as Message | undefined;
    expect(toolMsg).toBeDefined();
    expect(JSON.stringify(toolMsg)).toContain("echo: hello");
  });

  it("captures tool exceptions as error results instead of crashing", async () => {
    const runner = new AgentRunner();
    const result = await runner.run({
      provider: scriptedProvider([
        toolReply([{ id: "t1", name: "boom", input: {} }]),
        textReply("recovered"),
      ]),
      model: "mock-model",
      tools: [boomTool],
      messages: [{ role: "user", content: "go" }],
      cwd: ".",
    });
    expect(result.stoppedBecause).toBe("done");
    expect(JSON.stringify(result.messages)).toContain("Tool error: kaboom");
  });

  it("flags unknown tools to the model", async () => {
    const runner = new AgentRunner();
    const result = await runner.run({
      provider: scriptedProvider([
        toolReply([{ id: "t1", name: "nope", input: {} }]),
        textReply("ok"),
      ]),
      model: "mock-model",
      tools: [echoTool],
      messages: [{ role: "user", content: "go" }],
      cwd: ".",
    });
    expect(JSON.stringify(result.messages)).toContain("Unknown tool: nope");
  });

  it("stops at maxTurns", async () => {
    const runner = new AgentRunner();
    // Always answers with a tool call -> the loop must cut off.
    const endless = scriptedProvider([
      toolReply([{ id: "t1", name: "echo", input: { text: "x" } }]),
    ]);
    const result = await runner.run({
      provider: endless,
      model: "mock-model",
      tools: [echoTool],
      messages: [{ role: "user", content: "loop forever" }],
      cwd: ".",
      maxTurns: 3,
    });
    expect(result.stoppedBecause).toBe("max_turns");
    expect(result.toolCalls).toBe(3);
  });

  it("stops when the token budget is exceeded", async () => {
    const runner = new AgentRunner();
    const fat = scriptedProvider([
      toolReply([{ id: "t1", name: "echo", input: { text: "x" } }]),
    ]);
    const result = await runner.run({
      provider: fat,
      model: "mock-model",
      tools: [echoTool],
      messages: [{ role: "user", content: "burn tokens" }],
      cwd: ".",
      tokenBudget: 5, // first reply already costs 15
      maxTurns: 10,
    });
    expect(result.stoppedBecause).toBe("budget");
    // The turn that crosses the budget still completes (requests can't be
    // preempted mid-flight); the budget prevents any further turns.
    expect(result.toolCalls).toBe(1);
  });

  it("emits lifecycle events", async () => {
    const events: string[] = [];
    const runner = new AgentRunner((e) => events.push(e.type));
    await runner.run({
      provider: scriptedProvider([
        toolReply([{ id: "t1", name: "echo", input: { text: "x" } }]),
        textReply("done"),
      ]),
      model: "mock-model",
      tools: [echoTool],
      messages: [{ role: "user", content: "go" }],
      cwd: ".",
    });
    expect(events).toEqual([
      "turn_start", "tool_start", "tool_end", "turn_end",
      "turn_start", "assistant_text", "turn_end",
    ]);
  });
});

// ---------------------------------------------------------------------------
// OpenAI-compatible wire format (offline via injected fetch)
// ---------------------------------------------------------------------------

describe("OpenAICompatProvider", () => {
  it("sends tools and parses tool_calls back", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const fakeFetch = (async (url: string | URL, init?: RequestInit) => {
      calls.push({ url: String(url), init: init as RequestInit });
      return new Response(
        JSON.stringify({
          model: "test-model",
          choices: [
            {
              message: {
                content: null,
                tool_calls: [
                  {
                    id: "call_1",
                    function: { name: "read_file", arguments: '{"path":"a.ts"}' },
                  },
                ],
              },
              finish_reason: "tool_calls",
            },
          ],
          usage: { prompt_tokens: 12, completion_tokens: 34 },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }) as typeof fetch;

    const provider = new OpenAICompatProvider({
      id: "test",
      label: "Test",
      baseUrl: "https://api.test/v1",
      apiKey: "sk-test",
      fetchImpl: fakeFetch,
    });

    const reply = await provider.chat({
      messages: [{ role: "user", content: "read a.ts" }],
      model: "test-model",
      tools: [
        {
          name: "read_file",
          description: "read",
          parameters: { type: "object", properties: { path: { type: "string" } }, required: ["path"] },
        },
      ],
    });

    expect(reply.toolCalls).toHaveLength(1);
    expect(reply.toolCalls[0]?.name).toBe("read_file");
    expect(reply.toolCalls[0]?.input).toEqual({ path: "a.ts" });
    expect(reply.stopReason).toBe("tool_use");
    expect(reply.usage.inputTokens).toBe(12);
    expect(reply.usage.outputTokens).toBe(34);

    const body = JSON.parse(String(calls[0]?.init.body)) as {
      tools?: unknown[];
      messages: Array<Record<string, unknown>>;
    };
    expect(body.tools).toHaveLength(1);
    expect(body.messages[0]?.role).toBe("user");
  });

  it("retries on 429 then succeeds", async () => {
    let attempts = 0;
    const fakeFetch = (async () => {
      attempts++;
      if (attempts === 1) {
        return new Response("rate limited", { status: 429, headers: { "retry-after": "0" } });
      }
      return new Response(
        JSON.stringify({
          choices: [{ message: { content: "hello" }, finish_reason: "stop" }],
          usage: { prompt_tokens: 1, completion_tokens: 1 },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }) as typeof fetch;

    const provider = new OpenAICompatProvider({
      id: "test",
      label: "Test",
      baseUrl: "https://api.test/v1",
      fetchImpl: fakeFetch,
      maxRetries: 3,
      deadlineMs: 10_000,
    });

    const reply = await provider.chat({
      messages: [{ role: "user", content: "hi" }],
      model: "m",
    });
    expect(attempts).toBe(2);
    expect(reply.content).toBe("hello");
  });

  it("gives up within the deadline on persistent 429s", async () => {
    const fakeFetch = (async () =>
      new Response("rate limited", { status: 429, headers: { "retry-after": "60" } })) as typeof fetch;

    const provider = new OpenAICompatProvider({
      id: "test",
      label: "Test",
      baseUrl: "https://api.test/v1",
      fetchImpl: fakeFetch,
      maxRetries: 10,
      deadlineMs: 50,
    });

    await expect(
      provider.chat({ messages: [{ role: "user", content: "hi" }], model: "m" }),
    ).rejects.toThrow(/Retries exhausted|HTTP 429/);
  });
});
