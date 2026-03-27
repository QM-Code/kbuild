# Coding Agent Bootstrap

## Overview

Familiarize yourself with this project by reading:

- README.md
- Any AGENTS.md instructions, if present
- CMakeLists.txt
- src/*               Source tree
- include/*           Public API (if present)

If the task touches a subproject, demo, package, or example that has its own
`README.md`, read that local `README.md` before making changes there.

If the task crosses repo boundaries, read the top-level `README.md` in each
target repo before editing.

## Projects

Ongoing projects can be found in `agent/projects/*.md`.

If any projects are found, present them to the operator after bootstrap is complete.

## Issues / Recommendations

If you notice issues or have recommendations about the codebase, bring them to the operator.

## Building with kbuild

- Always use `kbuild` for builds. Do not use raw `cmake` commands for normal build flows.
- Always run from the repo root, invoking `kbuild` from that directory.
- Use `kbuild --help` to inspect the available options.
- `kbuild` with no arguments also prints usage; it does not build.
- `kbuild --build-latest` builds the core SDK/app into `build/latest/` and then builds demos listed in `build.defaults.demos` (if defined).
- Use `kbuild --build-demos [demo ...]` for explicit demo builds.
- With no demo names, `--build-demos` uses `build.demos`.
- Use `kbuild --clean <version>` or `kbuild --clean-latest` before rebuilding when you need a fresh build tree.

## Testing

- Prefer end-to-end checks using demo binaries under `demo/*/build/<version>/`.
- Add scripted test cases for demo usage under `tests/` or `cmake/tests/` as appropriate.
- Keep unit-style tests focused and explicit.

## Rules and Regulations

- **Always plan first**
- **Discuss, then code**
- Do not jump straight to coding when given a prompt. Consult with the operator and propose a structured plan before making code changes.
- If you have not been given an explicit instruction to begin coding, do not start coding.
- Do not interpret questions starting with "Can I/we/you...?" or "Is it possible to...?" as instructions to begin coding. Answer first, then ask whether to proceed.
- Always provide a summary of changes when you are finished.
