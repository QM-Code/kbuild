# Command Guide

This page is the fast path through the `kbuild.py` command surface. For the
full option-by-option reference, see [kbuild.md](kbuild.md).

## Command Groups

| Group | Purpose |
| --- | --- |
| bootstrap | point a thin wrapper at the shared `kbuild` checkout and create starter config |
| build | configure, build, and install the core SDK/app and optionally demos |
| clean | remove retained build slots safely |
| git | initialize or sync a repo rooted at the current directory |
| vcpkg | prepare repo-local `vcpkg` and sync the manifest baseline |

## Bootstrap Commands

```bash
./kbuild.py --kbuild-root /path/to/kbuild
./kbuild.py --kbuild-config
./kbuild.py --kbuild-init
```

What they do:

- `--kbuild-root <dir>` validates a shared `kbuild` checkout and writes
  `./.kbuild.json`.
- `--kbuild-config` creates a starter `kbuild.json`.
- `--kbuild-init` scaffolds a new repo from `kbuild.json` and the template set
  in this repository.

## Build Commands

Normal build:

```bash
./kbuild.py --build-latest
```

Alternate slot:

```bash
./kbuild.py --build dev
```

Explicit demo builds:

```bash
./kbuild.py --build-demos
./kbuild.py --build-demos sdk/alpha sdk/beta exe/core
```

Important behavior:

- Core output is `build/<slot>/`.
- SDK install output is `build/<slot>/sdk`.
- Demo output is `demo/<demo>/build/<slot>/`.
- `--build-demos` with no demo names uses `build.demos`.
- `--build-latest` can auto-build demos from `build.defaults.demos`.

## CMake Build Controls

```bash
./kbuild.py --build-latest --cmake-configure
./kbuild.py --build-latest --cmake-no-configure
./kbuild.py --build-latest --cmake-jobs 8
./kbuild.py --build dev --cmake-linkage both
```

Rules:

- `--cmake-configure` forces configure for the current run.
- `--cmake-no-configure` requires an existing `CMakeCache.txt`.
- `--cmake-jobs <n>` overrides configured job count.
- `--cmake-linkage <t>` accepts `static`, `shared`, or `both`.

## Clean Commands

```bash
./kbuild.py --build-list
./kbuild.py --clean-latest
./kbuild.py --clean dev
./kbuild.py --clean-all
```

Clean behavior is intentionally conservative:

- slot names must be simple tokens
- removal is restricted to expected `build/` and `demo/*/build/` layouts
- symlinked build directories are refused

## Git Commands

```bash
./kbuild.py --git-initialize
./kbuild.py --git-sync "Update docs"
```

Important behavior:

- `--git-initialize` verifies remote reachability and non-interactive auth,
  initializes `main`, creates the first commit, and pushes `origin/main`.
- `--git-sync` only works when `./.git` exists and the current directory is the
  git worktree root.

## Vcpkg Commands

```bash
./kbuild.py --vcpkg-install
./kbuild.py --vcpkg-sync-baseline
```

Important behavior:

- `--vcpkg-install` clones or verifies `./vcpkg/src`, bootstraps it, ensures
  repo-local cache directories, syncs the manifest baseline, then continues the
  normal build flow.
- `--vcpkg-sync-baseline` updates `vcpkg/vcpkg.json` from the current
  `./vcpkg/src` HEAD commit.

## Combination Rules

`kbuild.py` is strict about command mixing.

- Root help commands such as `--kbuild`, `--cmake`, `--git`, `--vcpkg`, and
  bare `--clean`/`--build` help forms must run alone.
- `--kbuild-config`, `--kbuild-init`, `--git-initialize`, `--git-sync`, and
  `--vcpkg-sync-baseline` are exclusive modes.
- Clean modes cannot be combined with build or git modes.
- Unknown flags and unexpected positional arguments hard-fail.

If you need the exhaustive matrix and all examples, use
[kbuild.md](kbuild.md).
