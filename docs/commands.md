# Command Guide

This page is the fast path through the `kbuild` command surface. For the full
option-by-option reference, see [kbuild.md](kbuild.md).

## Command Groups

| Group | Purpose |
| --- | --- |
| bootstrap | create starter config and scaffold a repo rooted at the current directory |
| build | configure, build, and install the core SDK/app and optionally demos |
| clean | remove retained build slots safely |
| git | initialize or sync a repo rooted at the current directory |
| vcpkg | prepare repo-local `vcpkg` and sync the manifest baseline |

## Bootstrap Commands

```bash
kbuild --kbuild-config
kbuild --kbuild-init
```

What they do:

- `--kbuild-config` creates a starter `./.kbuild.json`.
- `--kbuild-init` scaffolds a new repo from the effective kbuild config.

## Build Commands

Normal build:

```bash
kbuild --build-latest
```

Alternate slot:

```bash
kbuild --build dev
```

Explicit demo builds:

```bash
kbuild --build-demos
kbuild --build-demos sdk/alpha sdk/beta exe/core
```

Important behavior:

- Core output is `build/<slot>/`.
- SDK install output is `build/<slot>/sdk`.
- Demo output is `demo/<demo>/build/<slot>/`.
- `--build-demos` with no demo names uses `build.demos`.
- `--build-latest` can auto-build demos from `build.defaults.demos`.

## CMake Build Controls

```bash
kbuild --build-latest --cmake-configure
kbuild --build-latest --cmake-no-configure
kbuild --build-latest --cmake-jobs 8
kbuild --build dev --cmake-linkage both
```

Rules:

- `--cmake-configure` forces configure for the current run.
- `--cmake-no-configure` requires an existing `CMakeCache.txt`.
- `--cmake-jobs <n>` overrides configured job count.
- `--cmake-linkage <t>` accepts `static`, `shared`, or `both`.

## Clean Commands

```bash
kbuild --build-list
kbuild --clean-latest
kbuild --clean dev
kbuild --clean-all
```

Clean behavior is intentionally conservative:

- slot names must be simple tokens
- removal is restricted to expected `build/` and `demo/*/build/` layouts
- symlinked build directories are refused

## Git Commands

```bash
kbuild --git-initialize
kbuild --git-sync "Update docs"
```

Important behavior:

- `--git-initialize` verifies configured remote access and non-interactive auth,
  initializes `main`, creates the first commit, and pushes `origin/main`.
- `--git-sync` only works when `./.git` exists and the current directory is the
  git worktree root.

## Vcpkg Commands

```bash
kbuild --vcpkg-install
kbuild --vcpkg-sync-baseline
```

Important behavior:

- `--vcpkg-install` clones or verifies `./vcpkg/src`, bootstraps it, ensures
  repo-local cache directories, syncs the manifest baseline, then continues the
  normal build flow.
- `--vcpkg-sync-baseline` updates `vcpkg/vcpkg.json` from the current
  `./vcpkg/src` HEAD commit.

## Combination Rules

`kbuild` is strict about command mixing.

- Root help commands such as `--kbuild`, `--cmake`, `--git`, `--vcpkg`, and
  bare `--clean`/`--build` help forms must run alone.
- `--kbuild-config`, `--kbuild-init`, `--git-initialize`, `--git-sync`, and
  `--vcpkg-sync-baseline` are exclusive modes.
- Clean modes cannot be combined with build or git modes.
- Unknown flags and unexpected positional arguments hard-fail.

If you need the exhaustive matrix and all examples, use
[kbuild.md](kbuild.md).
