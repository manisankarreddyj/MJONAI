# ARCHIVE STATUS: NEVER SHIPPED, PRESERVED (2026-09-03)

Dart/Flutter shell ("tactical cockpit", dynamic-island HUD, haptic kill slider) — 6 files,
scaffold-stage, **never wired to the API, never shipped, zero references from runtime code**.

- **Why archived:** ADR-0007 (ACCEPTED, owner) sets the ladder: Android via **PWA
  Add-to-Home-Screen now**; a native Expo/React-Native shell only "if/when PWA limits bite
  (e.g. background refresh)", consuming the SAME API. A parallel Flutter shell was not the
  chosen path and had no CI/build path in the repo.
- **If the native-shell day comes:** read the component ideas here, then build on the
  ADR-0007 ladder (Expo/RN or Flutter against the FastAPI app API) — don't resurrect this
  tree as-is.

Evidence: `planning/decisions/ADR-0007-interactive-application.md` (decision 3).
