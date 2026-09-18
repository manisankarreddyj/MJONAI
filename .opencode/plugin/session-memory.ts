// Session-memory capture plugin (ADR-0009, layer-3 convenience).
//
// Auto-handoff raw trail: appends each captured user/assistant turn to
// cache/sessions/<YYYY-MM-DD>.jsonl through the deterministic
// tools/scripts/session_memory.py utility (which redacts secrets). The
// distilled authoritative truth remains MJONAI_DOCS.md section 16, produced by
// the /handoff command. This plugin only keeps the raw log current.
//
// Non-fatal by design: any capture failure is swallowed so a session never
// breaks because of logging.
import type { Plugin } from "@opencode-ai/plugin";
import { existsSync } from "node:fs";
import { join } from "node:path";

type TextPartLike = {
  id?: string;
  sessionID?: string;
  messageID?: string;
  type?: string;
  text?: string;
  synthetic?: boolean;
};

export default (async ({ directory, worktree, $ }) => {
  const root = directory || worktree || process.cwd();
  const isWin = process.platform === "win32";
  const venvPython = join(root, ".venv", ...(isWin ? ["Scripts", "python.exe"] : ["bin", "python"]));
  const python = existsSync(venvPython) ? venvPython : isWin ? "python" : "python3";
  const script = join(root, "tools", "scripts", "session_memory.py");

  const encoder = new TextEncoder();

  const append = async (role: "user" | "assistant", text: string): Promise<void> => {
    const body = (text ?? "").trim();
    if (!body || typeof $ !== "function") return;
    try {
      const proc = $`${python} ${script} append --role ${role} --text -`.cwd(root).quiet().nothrow();
      const writer = proc.stdin.getWriter();
      await writer.write(encoder.encode(body));
      await writer.close();
      await proc;
    } catch {
      // Non-fatal: capture is best-effort.
    }
  };

  const parts = new Map<string, Required<Pick<TextPartLike, "id" | "messageID" | "sessionID">> & TextPartLike>();
  const appendedPartIds = new Set<string>();
  const seenUserMessageIds = new Set<string>();

  const flushMessage = async (messageID: string): Promise<void> => {
    const pending = [...parts.values()].filter(
      (p) => p.messageID === messageID && !appendedPartIds.has(p.id),
    );
    if (!pending.length) return;
    for (const p of pending) appendedPartIds.add(p.id);
    await append("assistant", pending.map((p) => p.text ?? "").join("\n\n"));
  };

  return {
    "chat.message": async (_input: any, output: any) => {
      try {
        const id: string | undefined = output?.message?.id;
        if (id && seenUserMessageIds.has(id)) return;
        if (id) seenUserMessageIds.add(id);
        const text = (output?.parts ?? [])
          .filter((p: TextPartLike) => p?.type === "text" && !p?.synthetic)
          .map((p: TextPartLike) => p.text ?? "")
          .filter(Boolean)
          .join("\n\n");
        await append("user", text);
      } catch {
        // Non-fatal.
      }
    },
    event: async (input: any) => {
      try {
        const event = input?.event;
        if (!event || typeof event.type !== "string") return;

        if (event.type === "message.part.updated") {
          const part: TextPartLike = event.properties?.part;
          if (part?.type === "text" && part.id && part.messageID && part.sessionID && part.text) {
            parts.set(part.id, {
              ...part,
              id: part.id,
              messageID: part.messageID,
              sessionID: part.sessionID,
            });
          }
          return;
        }

        if (event.type === "message.updated") {
          const info = event.properties?.info;
          if (info?.role === "assistant" && info.id && info.time?.completed) {
            await flushMessage(info.id);
          }
          return;
        }

        if (event.type === "session.idle") {
          const sessionID: string | undefined = event.properties?.sessionID;
          const messageIDs = new Set(
            [...parts.values()]
              .filter((p) => !sessionID || p.sessionID === sessionID)
              .map((p) => p.messageID),
          );
          for (const messageID of messageIDs) await flushMessage(messageID);
          for (const id of [...parts.keys()]) {
            const p = parts.get(id);
            if (p && (!sessionID || p.sessionID === sessionID)) parts.delete(id);
          }
        }
      } catch {
        // Non-fatal.
      }
    },
  };
}) satisfies Plugin;
