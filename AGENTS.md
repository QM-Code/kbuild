# kbuild

`kbuild` is the shared build and project orchestration implementation for
ktools-style workspaces and components. `README.md` is for operators and
implementers using the tool; this file is for developers changing the `kbuild`
codebase itself.

## Start Here

1. Read `README.md` for the operator-facing model and supported workflows.
2. Read `docs/index.md` and `docs/kbuild.md` before changing CLI behavior,
   config handling, or project bootstrapping.
3. If you are working in a specific backend, read the relevant backend module
   and any backend-specific docs before editing behavior.

## Repository Map

- `kbuild.py`: executable entry script, commonly symlinked on `PATH` as
  `kbuild`
- `libs/kbuild/`: shared Python implementation and backend dispatch
- `libs/kbuild/*_backend.py`: backend-specific behavior for CMake, Cargo, Java,
  Swift, Kotlin, C#, and JavaScript
- `templates/`: scaffolding emitted by `--kbuild-init`
- `docs/`: user-facing documentation that must stay aligned with behavior

## Working Rules

- Preserve the command model: strict config validation, predictable directory
  layout, and strict command combinations are part of the tool's contract.
- Keep user-facing usage guidance in `README.md` and `docs/`. Put
  project-working
  instructions in `AGENTS.md`, not in `README.md`.
- When changing flags, config keys, init scaffolding, or backend behavior,
  update the affected docs in the same change.
- Treat `templates/` as product code. Template changes alter newly scaffolded
  projects, so verify placeholder names, generated paths, and accompanying docs.
- `--kbuild-init` currently scaffolds CMake-based projects only. Do not widen docs
  or assumptions beyond that unless the implementation changes end to end.

## Cross-Repo Context

- If a task crosses into another ktools workspace or generated component,
  read that
  area's local `AGENTS.md` and `README.md` before editing.
- Do not treat one backend as canonical for all others unless the shared docs
  or code explicitly establish that contract.
