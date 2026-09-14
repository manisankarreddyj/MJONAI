// Session-memory capture plugin (ADR-0009, layer-3 convenience).
// Appends every chat turn to cache/sessions/<YYYY-MM-DD>.jsonl via the
// deterministic tools/scripts/session_memory.py utility (redacts secrets,
// never authoritative). Startup auto-load is handled by opencode.json
// `instructions`; the `event` hook records checkpoints at session boundaries.
//
// Non-fatal by design: a capture failure must never break a session.
import type { Plugin } from "@opencode-ai/plugin";
import { join } from "node:path";

type PluginInput = {
  client: unknown;
  project?: string;
  directory?: string;
  $: (strings: TemplateStringsArray, ...args: unknown[]) => {
    quiet(): { nothrow(): Promise<void> };
  };
};

type HookEvent = { type?: string; event?: string } | string;

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

export default (async ({ project, $ }: PluginInput) => {
  const root = project ?? process.cwd();
  const python = join(root, ".venv", "Scripts", "python.exe");
  const script = join(root, "tools", "scripts", "session_memory.py");

  return {
    "chat.message": async (input: unknown) => {
      const msg =
        input && typeof input === "object" && "message" in input
          ? (input as Record<string, unknown>).message
          : input;
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
    event: async (event: HookEvent) => {
      const type = eventType(event);
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
  };
}) satisfies Plugin;