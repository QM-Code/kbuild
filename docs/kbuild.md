# kbuild.py Master Usage Guide

This is a complete operator guide for `kbuild.py` as implemented in this repository today.

Use this guide as a one-stop reference for:
- bootstrapping from an empty directory
- configuring `kbuild.json`
- building SDKs and demos
- wiring multiple SDK dependencies
- managing local vcpkg
- running repo/git helper modes safely

## 0) Agent Bootstrap Runbook (Read This First)

If you are an agent and need a deterministic “do the right thing” sequence, use this section.

### Agent decision flow

1. Confirm you are in the script directory.
2. If `kbuild.json` is missing, run `./kbuild.py --create-config` and stop for config edits.
3. If the task is “scaffold repo”, run `./kbuild.py --initialize-repo`.
4. If the task is “set up git remote”, run `./kbuild.py --initialize-git`.
5. If `kbuild.json` contains `vcpkg`, run `./kbuild.py --install-vcpkg` once.
6. For normal development builds, run `./kbuild.py`.
7. For demo validation, run `./kbuild.py --build-demos`.
8. For fast rebuild loops, run `./kbuild.py --no-configure` (and `--build-demos --no-configure` as needed).

### Agent-safe default command sequence

For most repos that already have config and CMake:

```bash
./kbuild.py && ./kbuild.py --build-demos
```

For repos with local vcpkg not yet prepared:

```bash
./kbuild.py --install-vcpkg
./kbuild.py && ./kbuild.py --build-demos
```

### Agent “do not guess” rules

- Do not invent new keys in `kbuild.json`; unknown keys hard-fail.
- Do not run mutually exclusive operational flags together.
- Do not use `--no-configure` unless a cache already exists.
- Do not assume demo names; use explicit names or `build.defaults.demos`.

## 1) Mental Model

`kbuild.py` has two big responsibilities:

1. Build orchestration.
   It validates `kbuild.json`, configures/builds core CMake targets into `build/<version>/`, installs SDK artifacts into `build/<version>/sdk`, and optionally builds demos in order.

2. Repo operations.
   It can generate a starter config, scaffold a new repo layout, initialize git against your configured remote, and run a simple add/commit/push sync.

`kbuild.py` is strict by design. Unknown flags, unexpected JSON keys, and path-traversal-like values are hard errors.

## 2) Non-Negotiable Rules

- Run `kbuild.py` from the same directory where the script is located.
- Keep `kbuild.json` valid and schema-compliant; unknown keys are rejected.
- Use simple version slot names (`latest`, `dev`, `ci`, `0.1`), not paths.
- Treat `--git-sync` as a broad operation (`git add .`).

## 3) Build Output Layout

Core build artifacts:
- Build tree: `build/<version>/`
- SDK install prefix: `build/<version>/sdk`

Demo build artifacts:
- Build tree: `demo/<demo>/build/<version>/`
- Optional demo SDK install prefix: `demo/<demo>/build/<version>/sdk`

Notes:
- Version defaults to `latest`.
- Demo SDK install prefix is only kept when the demo defines CMake install rules.

## 4) Option Reference (Complete)

Every option below includes what it does, how it behaves, and an example.

### `-h`, `--help`

Prints usage and exits with success. This mode does not parse or validate `kbuild.json` and does not perform any build work.

Example:

```bash
./kbuild.py --help
```

### `--list-builds`

Scans and prints existing version directories in both core and demo trees. It looks under `./build/*` and `./demo/**/build/*`, then prints normalized `./.../` paths. Use this before cleanup or when auditing retained slots.

Example:

```bash
./kbuild.py --list-builds
```

### `--remove-latest`

Deletes every `latest` slot in core and demos: `./build/latest/` and `./demo/**/build/latest/`. The script has safety checks and refuses paths that do not match expected layout or are symlinked in unsafe ways.

Example:

```bash
./kbuild.py --remove-latest
```

### `--version <name>`

Selects the build slot name (default is `latest`). The value must be a simple token with no slashes and no traversal (`..`). This affects both core and demo build directories.

Example:

```bash
./kbuild.py --version ci
```

### `--build-demos [demo ...]`

Builds demos after core SDK build succeeds.

Behavior:
- If demo names are provided, those demos are built in the provided order.
- If no demo names are provided, it uses `kbuild.json -> build.defaults.demos`.
- Demo tokens are normalized so `executable` and `demo/executable` both resolve.
- Requires `cmake.sdk.package_name` to be present.

The demo order is important because demo SDK prefixes from earlier entries can become available to later demo entries.

Examples:

```bash
./kbuild.py --build-demos
./kbuild.py --build-demos executable
./kbuild.py --build-demos libraries/alpha libraries/beta executable
```

### `--configure`

Forces CMake configure before build, overriding `cmake.configure_by_default` for the current run. Use when dependency paths, toolchain settings, or CMake options changed.

Example:

```bash
./kbuild.py --configure
```

### `--no-configure`

Skips configure and builds from existing cache. This requires an existing `CMakeCache.txt` in the target build directory, otherwise it fails. Use for fast incremental rebuilds when configuration is stable.

Example:

```bash
./kbuild.py --no-configure
```

### `--create-config`

Creates a starter `kbuild.json` template in the current directory. This only works when `kbuild.json` does not already exist, and it cannot be combined with other options.

Example:

```bash
./kbuild.py --create-config
```

### `--initialize-repo`

Scaffolds a new repository layout from `kbuild.json` metadata. This mode is strict: the directory must be empty except for `kbuild.py` and `kbuild.json`.

It creates directories and starter files such as:
- `CMakeLists.txt`
- `README.md`
- `.gitignore`
- `agent/BOOTSTRAP.md`
- `src/<project_id>.cpp`
- `vcpkg/vcpkg.json`
- `vcpkg/vcpkg-configuration.json`
- plus SDK-related files if `cmake.sdk.package_name` is defined

Example:

```bash
./kbuild.py --initialize-repo
```

### `--initialize-git`

Initializes local git repository state and pushes `main` to configured remote.

Behavior:
- Verifies remote reachability (`git.url`) and auth push preflight (`git.auth`) non-interactively.
- Fails if already inside a git worktree.
- Creates initial commit and pushes `main`.

Example:

```bash
./kbuild.py --initialize-git
```

### `--git-sync <msg>`

Runs a full sync sequence: `git add .`, `git commit -m <msg>`, `git push`. This is intentionally broad; it stages everything in the worktree.

Example:

```bash
./kbuild.py --git-sync "Update build docs"
```

### `--sync-vcpkg-baseline`

Reads `./vcpkg/src` HEAD commit hash and writes it into:
- `vcpkg/vcpkg.json` -> `builtin-baseline`
- `vcpkg/vcpkg-configuration.json` -> `default-registry.baseline`

Also ensures `default-registry.kind` exists (defaults to `builtin` if missing).

Example:

```bash
./kbuild.py --sync-vcpkg-baseline
```

### `--install-vcpkg`

Ensures local vcpkg checkout/bootstrap under repo-local `./vcpkg/src`, ensures local cache directories under `./vcpkg/build`, syncs baseline, then continues normal build flow.

Behavior details:
- If `kbuild.json` has a `vcpkg` section, install/bootstrap/sync is active.
- If `vcpkg` section is absent, this flag effectively becomes a no-op for setup.

Example:

```bash
./kbuild.py --install-vcpkg
```

## 5) Option Combination Rules

`kbuild.py` enforces mode exclusivity:

- `--create-config` cannot be combined with any other option.
- `--list-builds` and `--remove-latest` cannot be combined.
- `--list-builds` and `--remove-latest` cannot be combined with build flags.
- `--initialize-repo` cannot be combined with build/list/remove/git flags.
- `--initialize-git` cannot be combined with other modes.
- `--git-sync` cannot be combined with other modes.
- `--sync-vcpkg-baseline` must run alone.

If both `--configure` and `--no-configure` are provided, the last one on the command line wins.

## 6) End-to-End Playbooks

## Playbook A: Empty Directory to Build-Ready Repo

1. Put `kbuild.py` into an empty directory.
2. Create template config.
3. Edit `kbuild.json` with real project metadata.
4. Initialize repo scaffold.
5. Initialize git remote.
6. Install vcpkg and build.

Commands:

```bash
./kbuild.py --create-config
# edit kbuild.json
./kbuild.py --initialize-repo
./kbuild.py --initialize-git
./kbuild.py --install-vcpkg
```

## Playbook B: Typical Existing Repo Day-to-Day

Build core SDK and then demos in default order:

```bash
./kbuild.py && ./kbuild.py --build-demos
```

Fast rebuild without reconfigure:

```bash
./kbuild.py --no-configure
./kbuild.py --build-demos --no-configure
```

## Playbook C: Multiple SDK Dependencies + Multiple Demos

Use `cmake.dependencies` with version-templated prefixes and build all dependencies in the same slot.

1. Build dependency SDK A in slot `dev`.
2. Build dependency SDK B in slot `dev`.
3. Build your project in slot `dev`, then demos.

Example sequence:

```bash
cd ../kcli
./kbuild.py --version dev

cd ../ktrace
./kbuild.py --version dev --install-vcpkg

cd ../myproject
./kbuild.py --version dev --install-vcpkg
./kbuild.py --version dev --build-demos
```

If your `kbuild.json` includes:

```json
"cmake": {
  "dependencies": {
    "KcliSDK": { "prefix": "../kcli/build/{version}/sdk" },
    "KTraceSDK": { "prefix": "../ktrace/build/{version}/sdk" }
  }
}
```

then `{version}` becomes `dev` in this example.

## 7) `kbuild.json` Full Reference

## Full schema example (all parsable keys)

```json
{
  "project": {
    "title": "Example Project",
    "id": "exampleproject"
  },
  "git": {
    "url": "https://github.com/your-org/exampleproject",
    "auth": "git@github.com:your-org/exampleproject.git"
  },
  "cmake": {
    "minimum_version": "3.20",
    "configure_by_default": true,
    "sdk": {
      "package_name": "ExampleProjectSDK"
    },
    "dependencies": {
      "KcliSDK": {
        "prefix": "../kcli/build/{version}/sdk"
      },
      "KTraceSDK": {
        "prefix": "../ktrace/build/{version}/sdk"
      }
    }
  },
  "vcpkg": {
    "dependencies": [
      "spdlog",
      "fmt"
    ]
  },
  "build": {
    "defaults": {
      "demos": [
        "libraries/alpha",
        "libraries/beta",
        "executable"
      ]
    }
  }
}
```

## Top-level keys

Allowed top-level keys are exactly:
- `project` (required)
- `git` (required)
- `cmake` (optional)
- `vcpkg` (optional)
- `build` (optional)

Any unexpected top-level key is a hard validation error.

## `project` object

### `project.title`

Required non-empty string. Used for generated README/scaffold text.

### `project.id`

Required non-empty string and must match C/C++ identifier regex: `[A-Za-z_][A-Za-z0-9_]*`.

It is used for generated namespace, header/source names, and other scaffold defaults.

## `git` object

### `git.url`

Required non-empty string. Used for remote reachability checks.

### `git.auth`

Required non-empty string. Used for authenticated git operations (`origin` setup and push flows).

## `cmake` object

If `cmake` is omitted, default build mode has no build plan and returns `Nothing to do.` after config validation.

### `cmake.minimum_version`

Optional string, validated if present. Primarily used by repo initialization templates (`--initialize-repo`) for generated `CMakeLists.txt` minimum version.

### `cmake.configure_by_default`

Optional boolean, default `true`. Controls default configure behavior for build operations.

### `cmake.sdk`

Optional object.

#### `cmake.sdk.package_name`

Required when `cmake.sdk` exists. Non-empty string naming the exported CMake package (for example `KcliSDK`).

Important:
- `--build-demos` requires this metadata.
- The value is used to generate and pass `-D<PackageName>_DIR` hints.

### `cmake.dependencies`

Optional object mapping dependency package names to objects.

Dependency entry format:

```json
"KTraceSDK": {
  "prefix": "../ktrace/build/{version}/sdk"
}
```

Rules:
- Dependency key must be a non-empty string.
- Dependency object currently supports only `prefix`.
- `prefix` must be a non-empty string.
- `{version}` token is replaced by active slot (from `--version`).
- Dependency package name cannot equal this repo's own `cmake.sdk.package_name`.

Validation performed:
- Prefix path must exist.
- Prefix must contain `include/` and `lib/`.
- Prefix must contain `lib/cmake/<Package>/<Package>Config.cmake`.

Consumption during build:
- Adds each resolved prefix to `CMAKE_PREFIX_PATH`.
- Adds `-D<Package>_DIR=<prefix>/lib/cmake/<Package>`.

## `vcpkg` object

If present, build flow expects repo-local vcpkg setup and injects toolchain integration.

### `vcpkg.dependencies`

Optional array of non-empty strings. Parsed/validated by `kbuild.py`, and also used by `--initialize-repo` to generate `vcpkg/vcpkg.json` dependencies.

Package install resolution happens later via CMake + manifest mode.

## `build` object

### `build.defaults`

Optional object for default build behavior values.

### `build.defaults.demos`

Optional array of non-empty strings. Used when `--build-demos` is provided with no explicit demo names.

## 8) Multi-SDK Demo Orchestration Deep Dive

During demo builds, `kbuild.py` composes `CMAKE_PREFIX_PATH` in this order:
- core SDK prefix: `build/<version>/sdk`
- inferred vcpkg triplet prefix: `build/<version>/installed/<triplet>`
- each resolved dependency SDK prefix from `cmake.dependencies`
- any already-built demo SDK prefix for demos earlier in the same order

This means demo order can intentionally represent dependency layering.

Example:

```bash
./kbuild.py --build-demos libraries/base libraries/ext executable
```

If `libraries/base` installs an SDK package and `libraries/ext` needs it, that order allows resolution in one pass.

## 9) vcpkg Behavior Deep Dive

When `vcpkg` config exists and build mode runs:
- local vcpkg must exist at `./vcpkg/src` and be bootstrapped
- toolchain is forced via `-DCMAKE_TOOLCHAIN_FILE=./vcpkg/src/scripts/buildsystems/vcpkg.cmake`
- environment is prepared:
  - `VCPKG_ROOT` set to local checkout
  - `VCPKG_DOWNLOADS` set to repo-local cache unless already defined
  - `VCPKG_DEFAULT_BINARY_CACHE` set to repo-local cache unless already defined

`--install-vcpkg` performs initial clone/bootstrap and baseline sync.

Baseline sync source of truth:
- commit hash from `git -C ./vcpkg/src rev-parse HEAD`

Files updated:
- `vcpkg/vcpkg.json` -> `builtin-baseline`
- `vcpkg/vcpkg-configuration.json` -> `default-registry.baseline`

## 10) Repo Initialization Details

`--initialize-repo` requires directory hygiene:
- allowed existing entries before run: only `kbuild.py`, `kbuild.json`
- any extra file/dir triggers a hard error

Generated structure always includes:
- `agent/`, `agent/projects/`
- `cmake/`, `demo/`, `src/`, `tests/`, `vcpkg/`
- root `CMakeLists.txt`, `README.md`, `.gitignore`
- `agent/BOOTSTRAP.md`
- `src/<project_id>.cpp`
- `vcpkg/vcpkg.json`, `vcpkg/vcpkg-configuration.json`

If `cmake.sdk.package_name` is defined, it also generates:
- `include/<project_id>.hpp`
- `cmake/<PackageName>Config.cmake.in`

## 11) Git Operation Details

`--initialize-git` does these checks/actions:
- verifies remote is reachable (`git ls-remote <git.url>`)
- performs auth preflight via dry-run push from temp repo to `git.auth`
- `git init`, set branch `main`
- set/add `origin` to `git.auth`
- create initial commit and push `-u origin main`

`--git-sync <msg>` is intentionally simple and strong:
- stages everything with `git add .`
- commits with your message
- pushes current branch to its upstream

## 12) Environment Variables Used by kbuild

`kbuild.py` reads or sets these during certain modes:
- `VCPKG_ROOT` (set for build when vcpkg is enabled)
- `VCPKG_DOWNLOADS` (set if not already present)
- `VCPKG_DEFAULT_BINARY_CACHE` (set if not already present)
- `VCPKG_INSTALLED_DIR` and `VCPKG_TARGET_TRIPLET` (fallback source for demo triplet inference)
- `GIT_TERMINAL_PROMPT=0` in non-interactive git/auth checks

## 13) Common Failure Cases and Fixes

### `Error: 'kbuild.json' does not exist.`

Create it first:

```bash
./kbuild.py --create-config
```

### `--no-configure requires an existing CMakeCache.txt`

Run with configure once, then retry:

```bash
./kbuild.py --configure
```

### `--build-demos requires SDK metadata`

Define `cmake.sdk.package_name` in `kbuild.json`.

### `sdk dependency package config not found`

Your `cmake.dependencies.<pkg>.prefix` path is wrong or dependency SDK is not built/installed yet. Build dependency in same slot and verify `<prefix>/lib/cmake/<pkg>/<pkg>Config.cmake` exists.

### `vcpkg has not been set up`

Initialize local vcpkg first:

```bash
./kbuild.py --install-vcpkg
```

### `--initialize-repo must be run from an empty directory`

Move existing files out or start in a clean directory containing only `kbuild.py` and `kbuild.json`.

### `unknown option '--xyz'`

The script has strict argument parsing. Re-check the option spelling in the option reference section and remove unsupported positional arguments (except demo names after `--build-demos`).

### `unexpected key in kbuild.json`

`kbuild.json` is schema-strict. Remove unknown keys and keep to the documented key set only.

## 14) Master Command Cheatsheet

Scaffold from zero:

```bash
./kbuild.py --create-config
./kbuild.py --initialize-repo
./kbuild.py --initialize-git
```

Core build + demos (default slot):

```bash
./kbuild.py && ./kbuild.py --build-demos
```

Core build + demos (custom slot):

```bash
./kbuild.py --version dev
./kbuild.py --version dev --build-demos
```

Install/update local vcpkg then build:

```bash
./kbuild.py --install-vcpkg
```

Sync vcpkg baseline only:

```bash
./kbuild.py --sync-vcpkg-baseline
```

List and clean latest slots:

```bash
./kbuild.py --list-builds
./kbuild.py --remove-latest
```

## 15) Final Advice for Multi-Repo SDK Stacks

Use one shared version slot name across related repos (`dev`, `ci`, `latest`) and keep dependency prefix templates version-aware (`{version}`). Build dependencies first, then consumers, then demos. That gives deterministic CMake prefix resolution and keeps your dependency graph reproducible.
