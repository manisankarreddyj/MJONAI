// Session-memory capture plugin (ADR-0009, layer-3 convenience).
// (1) Best-effort per-message capture into cache/sessions/<YYYY-MM-DD>.jsonl
// via the deterministic tools/scripts/session_memory.py utility (redacts
// secrets, never authoritative). (2) `session.idle` checkpoint markers.
// (3) `experimental.session.compacting` injects the §16 memory pointer so a
// compacted session still knows where durable state lives. Startup auto-load
// is handled by opencode.json `instructions`.
//
// Non-fatal by design: a capture failure must never break a session.
import type { Plugin } from "@opencode-ai/plugin";
import { join } from "node:path";

type PluginInput = {
  client: unknown;
  project?: unknown;
  directory?: string;
  worktree?: string;
  $: (strings: TemplateStringsArray, ...args: unknown[]) => {
    quiet(): { nothrow(): Promise<void> };
  };
};

type HookEvent = { type?: string; event?: string } | string;

function resolveRoot(input: PluginInput): string {
  if (typeof input.project === "string") return input.project;
  return input.directory ?? input.worktree ?? process.cwd();
}

function textOf(value: unknown): string | undefined {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    const parts = value
      .map((p) =>
        p && typeof p === "object"
          ? (p as { type?: string; text?: string }).type === "text"
            ? (p as { text?: string }).text ?? ""
            : ""
      )
      .filter(Boolean);
    return parts.length ? parts.join("\n") : undefined;
  }
  if (value && typeof value === "object") {
    for (const key of ["text", "content", "message", "input", "prompt"]) {
      const found = textOf((value as Record<string, unknown>)[key]);
      if (found !== undefined) return found;
    }
  }
  return undefined;
}

function messageRole(message: unknown): "user" | "assistant" {
  const role =
    message && typeof message === "object"
      ? (message as Record<string, unknown>).role
      : undefined;
  return role === "user" ? "user" : "assistant";
}

function eventType(event: HookEvent): string {
  if (typeof event === "string") return event;
  return String(event?.type ?? event?.event ?? "");
}

function unwrapEvent(input: unknown): unknown {
  if (
    input &&
    typeof input === "object" &&
    (input as Record<string, unknown>).event &&
    typeof (input as Record<string, unknown>).event === "object"
  ) {
    return (input as Record<string, unknown>).event;
  }
  return input;
}

export default (async (input: PluginInput) => {
  const root = resolveRoot(input);
  const python = join(root, ".venv", "Scripts", "python.exe");
  const script = join(root, "tools", "scripts", "session_memory.py");
  const { $ } = input;

  return {
    "chat.message": async (chatInput: unknown) => {
      const msg =
        chatInput && typeof chatInput === "object" && "message" in chatInput
          ? (chatInput as Record<string, unknown>).message
          : chatInput;
      const text = textOf(msg);
      if (!text) return;
      const safe = text.replaceAll("\n", " ").slice(0, 4000);
      try {
        await $`${python} ${script} append --role ${messageRole(msg)} --text ${safe}`
          .quiet()
          .nothrow();
      } catch {
        // non-fatal
      }
    },
    event: async (rawEvent: unknown) => {
      const type = eventType(unwrapEvent(rawEvent) as HookEvent);
      if (type.includes("session.idle") || type.includes("session.end")) {
        try {
          await $`${python} ${script} append --role system --text "== session checkpoint =="`
            .quiet()
            .nothrow();
        } catch {
          // non-fatal
        }
      }
    },
    "experimental.session.compacting": async (_compactionInput: unknown, output: unknown) => {
      try {
        const out = output as { context?: string[] };
        if (Array.isArray(out.context)) {
          out.context.push(
            [
              "## Session Memory",
              "Durable project state lives in MJONAI_DOCS.md section 16 (auto-loaded already).",
              "Raw per-message logs are captured to cache/sessions/ (gitignored).",
              "When writing your continuation summary, carry forward: where things stand, the",
              "P0/P1/P2 action lists, and any open owner decisions — do not re-derive them.",
            ].join("\n")
          );
        }
      } catch {
        // non-fatal
      }
    },
  };
}) satisfies Plugin;