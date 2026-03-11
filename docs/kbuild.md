# Kbuild Full Reference

This is the exhaustive operator guide for `kbuild.py` as implemented in this
repository today.

If you want the shorter docs set first, start with:

- [Overview and quick start](index.md)
- [Command guide](commands.md)
- [Config guide](config.md)
- [Common workflows](workflows.md)

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
2. If `./.kbuild.json` is missing, run `./kbuild.py --kbuild-root <directory>` and stop.
3. If `./kbuild.json` is missing, run `./kbuild.py --kbuild-config` and stop for config edits.
4. If the task is “scaffold repo”, run `./kbuild.py --kbuild-init`.
5. If the task is “set up git remote”, run `./kbuild.py --git-initialize`.
6. If `kbuild.json` contains `vcpkg`, run `./kbuild.py --vcpkg-install` once.
7. For normal development builds, run `./kbuild.py --build-latest`.
8. For explicit demo-only validation, run `./kbuild.py --build-demos`.
9. For fast rebuild loops, run `./kbuild.py --build-latest --cmake-no-configure` (and `--build-demos --cmake-no-configure` as needed).

### Agent-safe default command sequence

For most repos that already have config and CMake:

```bash
./kbuild.py --build-latest
```

For repos with local vcpkg not yet prepared:

```bash
./kbuild.py --vcpkg-install
```

### Agent “do not guess” rules

- Do not invent new keys in `kbuild.json`; unknown keys hard-fail.
- Do not run mutually exclusive operational flags together.
- Do not use `--cmake-no-configure` unless a cache already exists.
- Do not assume demo names; use explicit names, `build.demos`, or `build.defaults.demos`.

## 1) Mental Model

`kbuild.py` has two big responsibilities:

1. Build orchestration.
   It validates `kbuild.json`, configures/builds core CMake targets into `build/<version>/`, installs SDK artifacts into `build/<version>/sdk`, and optionally builds demos in order.

2. Repo operations.
   It can generate a starter config, scaffold a new repo layout, initialize git against your configured remote, run a simple add/commit/push sync, and batch-forward commands into child repos.

`kbuild.py` is strict by design. Unknown flags, unexpected JSON keys, and path-traversal-like values are hard errors.

## 2) Non-Negotiable Rules

- Run `kbuild.py` from the same directory where the script is located.
- Keep `kbuild.json` valid and schema-compliant; unknown keys are rejected.
- Use simple version slot names (`latest`, `dev`, `ci`, `0.1`), not paths.
- `--git-sync` only operates on a repo rooted at the current directory; it fails without local `./.git`.
- `--batch` runs the remaining args inside child repos; with no inline repo list it uses `kbuild.json -> batch.repos`.

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

Prints usage and exits with success. `./kbuild.py` with no arguments does the same thing. This mode does not parse or validate `kbuild.json` and does not perform any build work.

Example:

```bash
./kbuild.py --help
```

### `--kbuild`

Prints only the kbuild/bootstrap option group and exits with success. This is a root help command; it must be run by itself.

Example:

```bash
./kbuild.py --kbuild
```

### `--kbuild-root <dir>`

Bootstraps the thin `kbuild.py` wrapper by validating a shared kbuild checkout and writing `./.kbuild.json` with `kbuild.root=<dir>`.

Behavior:
- The command validates the target by loading the shared library from `<dir>/libs`.
- It must be run by itself; it cannot be combined with other options.
- It is the first required step for a fresh directory that only contains `kbuild.py`.

Example:

```bash
./kbuild.py --kbuild-root /path/to/kbuild
```

### `--build-list`

Scans and prints existing version directories in both core and demo trees. It looks under `./build/*` and `./demo/**/build/*`, then prints normalized `./.../` paths. Use this before cleanup or when auditing retained slots.

Example:

```bash
./kbuild.py --build-list
```

### `--clean`

Prints only the clean option group and exits with success. This is a root help command; it must be run by itself.

Example:

```bash
./kbuild.py --clean
```

### `--clean <name>`

Removes the specified build slot from both core and demos. The value must be a simple token with no slashes and no traversal (`..`).

Example:

```bash
./kbuild.py --clean ci
```

### `--clean-latest`

Deletes every `latest` slot in core and demos: `./build/latest/` and `./demo/**/build/latest/`. The script has safety checks and refuses paths that do not match expected layout or are symlinked in unsafe ways.

Example:

```bash
./kbuild.py --clean-latest
```

### `--clean-all`

Deletes every build slot in both core and demo trees.

Example:

```bash
./kbuild.py --clean-all
```

### `--build <name>`

Selects the build slot name. The value must be a simple token with no slashes and no traversal (`..`). This affects both core and demo build directories.

Example:

```bash
./kbuild.py --build ci
```

With no version argument, `--build` prints only the build option group and exits with success.

### `--build-latest`

Builds the `latest` slot explicitly.

Example:

```bash
./kbuild.py --build-latest
```

### `--build-demos [demo ...]`

Builds demos after core SDK build succeeds.

Behavior:
- If demo names are provided, those demos are built in the provided order.
- If no demo names are provided, it uses `kbuild.json -> build.demos`.
- Demo tokens are normalized so `exe/core` and `demo/exe/core` both resolve.
- Requires `cmake.sdk.package_name` to be present.
- If `kbuild.json` has a `vcpkg` section, demos inherit the same vcpkg installed tree/triplet as the core build.
- If `kbuild.json` does not have a `vcpkg` section, demos do not require or search for vcpkg.

The demo order is important because demo SDK prefixes from earlier entries can become available to later demo entries.

Examples:

```bash
./kbuild.py --build-demos
./kbuild.py --build-demos exe/core
./kbuild.py --build-demos sdk/alpha sdk/beta exe/core
```

### `--cmake`

Prints only the CMake option group and exits with success. This is a root help command; it must be run by itself.

Example:

```bash
./kbuild.py --cmake
```

### `--cmake-configure`

Forces CMake configure before build, overriding `cmake.configure_by_default` for the current run. Use when dependency paths, toolchain settings, or CMake options changed.

Example:

```bash
./kbuild.py --cmake-configure
```

### `--cmake-no-configure`

Skips configure and builds from existing cache. This requires an existing `CMakeCache.txt` in the target build directory, otherwise it fails. Use for fast incremental rebuilds when configuration is stable.

Example:

```bash
./kbuild.py --cmake-no-configure
```

### `--cmake-jobs <n>`

Overrides the parallel job count used for `cmake --build`. The value must be a positive integer.

Example:

```bash
./kbuild.py --build-latest --cmake-jobs 8
```

### `--cmake-linkage <t>`

Overrides the configured build linkage for the current run. Allowed values are `static`, `shared`, or `both`.

This controls the generated `-D<PROJECT>_BUILD_STATIC` / `-D<PROJECT>_BUILD_SHARED` options used by the root build and demo builds.

Example:

```bash
./kbuild.py --build-latest --cmake-linkage both
```

### `--kbuild-config`

Creates a starter `kbuild.json` template in the current directory. Run `./kbuild.py --kbuild-root <dir>` first so the wrapper can load the shared library. This only works when `kbuild.json` does not already exist, and it cannot be combined with other options. The starter template omits the optional `vcpkg` object; add it only when the repo actually uses vcpkg.

Example:

```bash
./kbuild.py --kbuild-config
```

### `--kbuild-init`

Scaffolds a new repository layout from `kbuild.json` metadata. `./kbuild.json` is required for this mode. The directory must otherwise be empty except for `kbuild.py`, `kbuild.json`, and `.kbuild.json`.

It creates directories and starter files such as:
- `CMakeLists.txt`
- `README.md`
- `.gitignore`
- `agent/BOOTSTRAP.md`
- `demo/bootstrap/{CMakeLists.txt,README.md,src/main.cpp}` (SDK projects)
- `demo/sdk/{alpha,beta,gamma}/...` (SDK projects)
- `demo/exe/{core,omega}/{CMakeLists.txt,README.md,src/main.cpp}` (SDK projects)
- `demo/*/cmake/tests/CMakeLists.txt` placeholders (SDK projects)
- `cmake/tests/CMakeLists.txt` (when `cmake` is defined in `kbuild.json`)
- `cmake/00_toolchain.cmake` (when `cmake` is defined in `kbuild.json`)
- `cmake/10_dependencies.cmake` (when `cmake` is defined in `kbuild.json`)
- `cmake/20_targets.cmake` (when `cmake` is defined in `kbuild.json`)
- `src/<project_id>.cpp`
- `vcpkg/vcpkg.json` (when `vcpkg` is defined in `kbuild.json`)
- plus SDK-related files if `cmake.sdk.package_name` is defined

Example:

```bash
./kbuild.py --kbuild-init
```

### `--git`

Prints only the git option group and exits with success. This is a root help command; it must be run by itself.

Example:

```bash
./kbuild.py --git
```

### `--git-initialize`

Initializes local git repository state and pushes `main` to configured remote.

Behavior:
- Verifies remote reachability (`git.url`) and auth push preflight (`git.auth`) non-interactively.
- Fails if `./.git` already exists or if the current directory already owns a git worktree.
- If the current directory sits inside a parent git worktree, initializes a new repo rooted at the current directory rather than adopting the parent.
- Creates initial commit and pushes `main`.

Example:

```bash
./kbuild.py --git-initialize
```

### `--git-sync <msg>`

Runs a full sync sequence rooted at the current directory's own git repo: `git add -A`, check for staged changes, then `git commit -m <msg>` and `git push` only when needed.

Safety checks:
- Requires local git metadata at `./.git`.
- Refuses to run if git resolves the worktree root to a parent directory.
- If staging produces no changes, it prints `No changes to commit.` and exits successfully.

Example:

```bash
./kbuild.py --git-sync "Update build docs"
```

### `--batch [repo ...]`

Runs the remaining command-line args in each target repo, in order.

Behavior:
- With inline repo args, use those repo paths relative to the current repo root.
- With no inline repo args, use `kbuild.json -> batch.repos`.
- Validates every target repo up front and then stops on the first child command failure.
- Forwards the remaining args exactly as written, minus the `--batch` clause itself.

Examples:

```bash
./kbuild.py --batch --build dev
./kbuild.py --batch kcli ktrace --build dev
./kbuild.py --batch --git-sync "Sync child repos"
```

### `--vcpkg`

Prints only the vcpkg option group and exits with success. This is a root help command; it must be run by itself.

Example:

```bash
./kbuild.py --vcpkg
```

### `--vcpkg-sync-baseline`

Reads `./vcpkg/src` HEAD commit hash and writes it into:
- `vcpkg/vcpkg.json` -> `configuration.default-registry.baseline`

Example:

```bash
./kbuild.py --vcpkg-sync-baseline
```

### `--vcpkg-install`

Ensures local vcpkg checkout/bootstrap under repo-local `./vcpkg/src`, ensures local cache directories under `./vcpkg/build`, syncs baseline, then continues normal build flow.

Behavior details:
- If `kbuild.json` has a `vcpkg` section, install/bootstrap/sync is active.
- If `vcpkg` section is absent, this flag effectively becomes a no-op for setup.

Example:

```bash
./kbuild.py --vcpkg-install
```

## 5) Option Combination Rules

`kbuild.py` enforces mode exclusivity:

- `--kbuild`, `--cmake`, `--git`, and `--vcpkg` are root help commands and must be run alone.
- `--kbuild-config` cannot be combined with any other option.
- `--build-list` cannot be combined with other modes.
- `--build` with no version prints only the build option group.
- Clean options (`--clean <version>`, `--clean-latest`, `--clean-all`) cannot be combined with build, git, or kbuild init/config options.
- `--clean` with no version prints only the clean option group.
- `--kbuild-init` cannot be combined with build/list/clean/git flags.
- `--git-initialize` cannot be combined with other modes.
- `--git-sync` cannot be combined with other modes.
- `--vcpkg-sync-baseline` must run alone.

If both `--cmake-configure` and `--cmake-no-configure` are provided, the last one on the command line wins.

## 6) End-to-End Playbooks

## Playbook A: Empty Directory to Build-Ready Repo

1. Put `kbuild.py` into an empty directory.
2. Point the wrapper at the shared kbuild library.
3. Create template config.
4. Edit `kbuild.json` with real project metadata.
5. Initialize repo scaffold.
6. Initialize git remote.
7. Install vcpkg and build.

Commands:

```bash
./kbuild.py --kbuild-root <path-to-kbuild>
./kbuild.py --kbuild-config
# edit kbuild.json
./kbuild.py --kbuild-init
./kbuild.py --git-initialize
./kbuild.py --vcpkg-install
```

## Playbook B: Typical Existing Repo Day-to-Day

Build core SDK and then demos in default order:

```bash
./kbuild.py --build-latest
```

Fast rebuild without reconfigure:

```bash
./kbuild.py --build-latest --cmake-no-configure
./kbuild.py --build-demos --cmake-no-configure
```

## Playbook C: Multiple SDK Dependencies + Multiple Demos

Use `cmake.dependencies` with version-templated prefixes and build all dependencies in the same slot.

1. Build dependency SDK A in slot `dev`.
2. Build dependency SDK B in slot `dev`.
3. Build your project in slot `dev`, then demos.

Example sequence:

```bash
cd ../kcli
./kbuild.py --build dev

cd ../ktrace
./kbuild.py --build dev --vcpkg-install

cd ../myproject
./kbuild.py --build dev --vcpkg-install
./kbuild.py --build dev --build-demos
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
    "demos": [
      "sdk/alpha",
      "sdk/beta",
      "exe/core"
    ],
    "defaults": {
      "demos": [
        "sdk/alpha",
        "sdk/beta",
        "exe/core"
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

Optional string, validated if present. Primarily used by repo initialization templates (`--kbuild-init`) for generated `CMakeLists.txt` minimum version.

### `cmake.configure_by_default`

Optional boolean, default `true`. Controls default configure behavior for build operations.

### `cmake.sdk`

Optional object.

#### `cmake.sdk.package_name`

Required when `cmake.sdk` exists. Non-empty string naming the exported CMake package (for example `KcliSDK`).

Important:
- All demo builds require this metadata (`--build-demos` and `build.defaults.demos` on `./kbuild.py --build-latest`).
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
- `{version}` token is replaced by active slot (from `--build`).
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

Optional array of non-empty strings. Parsed/validated by `kbuild.py`, and also used by `--kbuild-init` to generate `vcpkg/vcpkg.json` dependencies when the `vcpkg` object is present.

Package install resolution happens later via CMake + manifest mode.

## `build` object

### `build.demos`

Optional array of non-empty strings. Used by `./kbuild.py --build-demos` when no explicit demo names are provided.

### `build.defaults`

Optional object for default build behavior values.

### `build.defaults.demos`

Optional array of non-empty strings. Used by `./kbuild.py --build-latest` (without `--build-demos`) to auto-build demos after core build succeeds.

## 8) Multi-SDK Demo Orchestration Deep Dive

During demo builds, `kbuild.py` composes `CMAKE_PREFIX_PATH` in this order:
- core SDK prefix: `build/<version>/sdk`
- inherited vcpkg triplet prefix: `build/<version>/installed/<triplet>` (only when `kbuild.json` defines `vcpkg`)
- each resolved dependency SDK prefix from `cmake.dependencies`
- any already-built demo SDK prefix for demos earlier in the same order

This means demo order can intentionally represent dependency layering.

Runtime path note:
- `kbuild.py` may also derive local runtime library directories from those prefixes and pass them into generated CMake as `KTOOLS_RUNTIME_RPATH_DIRS`.
- Generated projects use that list for `BUILD_RPATH` so shared-library demos and local SDK builds can run from build trees without extra loader setup.
- Installed artifacts do not mirror those absolute local directories into `INSTALL_RPATH`.
- Self-contained or relocatable packaging is a separate concern and is not implied by the default generated install layout.

Example:

```bash
./kbuild.py --build-demos sdk/base sdk/ext exe/core
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
- demo builds inherit the same core-build `installed/<triplet>` prefix

`--vcpkg-install` performs initial clone/bootstrap and baseline sync.

Baseline sync source of truth:
- commit hash from `git -C ./vcpkg/src rev-parse HEAD`

Files updated:
- `vcpkg/vcpkg.json` -> `configuration.default-registry.baseline`

## 10) Repo Initialization Details

`--kbuild-init` requires directory hygiene:
- allowed existing entries before run: only `kbuild.py`, `kbuild.json`, `.kbuild.json`
- any extra file/dir triggers a hard error

Generated structure always includes:
- `agent/`, `agent/projects/`
- `cmake/`, `demo/`, `src/`, `tests/`
- root `CMakeLists.txt`, `README.md`, `.gitignore`
- `agent/BOOTSTRAP.md`
- `src/<project_id>.cpp`

If `vcpkg` is defined in `kbuild.json`, it also generates:
- `vcpkg/`
- `vcpkg/vcpkg.json`

If `cmake` is defined in `kbuild.json`, it also generates:
- `cmake/tests/CMakeLists.txt`
- `cmake/00_toolchain.cmake`
- `cmake/10_dependencies.cmake`
- `cmake/20_targets.cmake`

If `cmake.sdk.package_name` is defined, it also generates:
- `cmake/50_install_export.cmake`
- `include/<project_id>.hpp`
- `cmake/<PackageName>Config.cmake.in`

## 11) Git Operation Details

`--git-initialize` does these checks/actions:
- verifies remote is reachable (`git ls-remote <git.url>`)
- performs auth preflight via dry-run push from temp repo to `git.auth`
- `git init`, set branch `main`
- set/add `origin` to `git.auth`
- create initial commit and push `-u origin main`

`--git-sync <msg>` is intentionally simple and strong, but only for the repo rooted at the current directory:
- requires local `./.git`
- refuses to use a parent/surrounding worktree
- stages everything with `git add -A`
- exits successfully without commit/push when staging produced no changes
- otherwise commits with your message
- then pushes current branch to its upstream

## 12) Environment Variables Used by kbuild

`kbuild.py` reads or sets these during certain modes:
- `VCPKG_ROOT` (set for build when vcpkg is enabled)
- `VCPKG_DOWNLOADS` (set if not already present)
- `VCPKG_DEFAULT_BINARY_CACHE` (set if not already present)
- `VCPKG_INSTALLED_DIR` and `VCPKG_TARGET_TRIPLET` (override source when resolving vcpkg-enabled build/demo context)
- `GIT_TERMINAL_PROMPT=0` in non-interactive git/auth checks

## 13) Common Failure Cases and Fixes

### `missing required local config file './.kbuild.json'`

Bootstrap the wrapper first:

```bash
./kbuild.py --kbuild-root <path-to-kbuild>
```

### `missing required config file './kbuild.json'`

Create it first:

```bash
./kbuild.py --kbuild-config
```

### `--cmake-no-configure requires an existing CMakeCache.txt`

Run with configure once, then retry:

```bash
./kbuild.py --cmake-configure
```

### `demo builds require SDK metadata`

Define `cmake.sdk.package_name` in `kbuild.json`.

### `sdk dependency package config not found`

Your `cmake.dependencies.<pkg>.prefix` path is wrong or dependency SDK is not built/installed yet. Build dependency in same slot and verify `<prefix>/lib/cmake/<pkg>/<pkg>Config.cmake` exists.

### `vcpkg has not been set up`

Initialize local vcpkg first:

```bash
./kbuild.py --vcpkg-install
```

### `--kbuild-init must be run from an empty directory`

Move existing files out or start in a clean directory containing only `kbuild.py`, `kbuild.json`, and `.kbuild.json`.

### `unknown option '--xyz'`

The script has strict argument parsing. Re-check the option spelling in the option reference section and remove unsupported positional arguments (except demo names after `--build-demos`).

### `unexpected key in kbuild.json`

`kbuild.json` is schema-strict. Remove unknown keys and keep to the documented key set only.

## 14) Master Command Cheatsheet

Scaffold from zero:

```bash
./kbuild.py --kbuild-root <path-to-kbuild>
./kbuild.py --kbuild-config
./kbuild.py --kbuild-init
./kbuild.py --git-initialize
```

Core build + demos (default slot):

```bash
./kbuild.py --build-latest
```

Core build + demos (custom slot):

```bash
./kbuild.py --build dev
```

Install/update local vcpkg then build:

```bash
./kbuild.py --vcpkg-install
```

Sync vcpkg baseline only:

```bash
./kbuild.py --vcpkg-sync-baseline
```

List and clean latest slots:

```bash
./kbuild.py --build-list
./kbuild.py --clean-latest
```

## 15) Final Advice for Multi-Repo SDK Stacks

Use one shared version slot name across related repos (`dev`, `ci`, `latest`) and keep dependency prefix templates version-aware (`{version}`). Build dependencies first, then consumers, then demos. That gives deterministic CMake prefix resolution and keeps your dependency graph reproducible.
