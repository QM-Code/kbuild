# Kbuild Full Reference

This is the exhaustive operator guide for `kbuild` as implemented in this
repository today.

If you want the shorter docs set first, start with:

- [Overview and quick start](index.md)
- [Command guide](commands.md)
- [Config guide](config.md)
- [Common workflows](workflows.md)

Use this guide as a one-stop reference for:

- bootstrapping from an empty directory
- configuring `.kbuild.json` and optional `kbuild.json`
- building SDKs and demos
- wiring multiple SDK dependencies
- managing local `vcpkg`
- running repo/git helper modes safely

## 0) Agent Bootstrap Runbook

### Agent decision flow

1. Confirm you are in the intended repo root.
2. If `./.kbuild.json` is missing and the task is repo bootstrap, run
   `kbuild --kbuild-config` and stop for config edits.
3. If `./.kbuild.json` is missing for any other task, stop. This is not a valid
   `kbuild` repo root.
4. If the task is “scaffold repo”, run `kbuild --kbuild-init`.
5. If the task is “set up git remote”, run `kbuild --git-initialize`.
6. If the effective config contains `vcpkg`, run `kbuild --vcpkg-install` once.
7. For normal development builds, run `kbuild --build-latest`.
8. For explicit demo-only validation, run `kbuild --build-demos`.
9. For fast rebuild loops, run `kbuild --build-latest --cmake-no-configure`
   and `kbuild --build-demos --cmake-no-configure` as needed.

### Agent “do not guess” rules

- Do not invent new keys in the kbuild config; unknown keys hard-fail.
- Do not run mutually exclusive operational flags together.
- Do not use `--cmake-no-configure` unless a cache already exists.
- Do not assume demo names; use explicit names, `build.demos`, or
  `build.defaults.demos`.

## 1) Mental Model

`kbuild` has two big responsibilities:

1. Build orchestration.
   It validates the effective config, configures/builds core CMake targets into
   `build/<version>/`, installs SDK artifacts into `build/<version>/sdk`, and
   optionally builds demos in order.

2. Repo operations.
   It can generate a starter config, scaffold a new repo layout, initialize git
   against your configured remote, run a simple add/commit/push sync, and
   batch-forward commands into child repos.

`kbuild` is strict by design. Unknown flags, unexpected JSON keys, missing repo
markers, and path-traversal-like values are hard errors.

## 2) Non-Negotiable Rules

- Run `kbuild` from a directory containing `./.kbuild.json`.
- `./.kbuild.json` is required for every command except `--kbuild-config`.
- `./kbuild.json` is optional and acts only as a base layer when present.
- Use simple version slot names (`latest`, `dev`, `ci`, `0.1`), not paths.
- `--git-sync` only operates on a repo rooted at the current directory and
  fails without local `./.git`.
- `--batch` runs the remaining args inside child repos; with no inline repo
  list it uses `batch.repos` from the effective config.

## 3) Config Model

`kbuild` reads:

- `./.kbuild.json` as the required repo marker and primary config
- `./kbuild.json` as an optional shared base config

Merge behavior:

- If only `.kbuild.json` exists, that file is the whole config.
- If both files exist, `.kbuild.json` deep-merges on top of `kbuild.json`.

Allowed top-level keys are exactly:

- `project`
- `git`
- `cmake`
- `vcpkg`
- `build`
- `batch`

Any unexpected top-level key is a hard validation error.

## 4) Build Output Layout

Core build artifacts:

- Build tree: `build/<version>/`
- SDK install prefix: `build/<version>/sdk`

Demo build artifacts:

- Build tree: `demo/<demo>/build/<version>/`
- Optional demo SDK install prefix: `demo/<demo>/build/<version>/sdk`

Notes:

- Version defaults to `latest`.
- Demo SDK install prefix is only kept when the demo defines CMake install
  rules.

## 5) Option Reference

### `-h`, `--help`

Prints usage and exits with success.

### `--kbuild`

Prints only the bootstrap option group and exits with success. Must run alone.

### `--kbuild-config`

Creates a starter `./.kbuild.json` template in the current directory.

Behavior:

- This is the only command allowed when `./.kbuild.json` is absent.
- It must run by itself.
- It fails if `./.kbuild.json` already exists.
- It does not create `./kbuild.json`.

Example:

```bash
kbuild --kbuild-config
```

### `--kbuild-init`

Scaffolds a new repository layout from the effective kbuild config.

Behavior:

- Requires `./.kbuild.json`.
- The directory must otherwise be empty except for `kbuild.json` and
  `.kbuild.json`.
- Uses the effective merged config, so `kbuild.json` may contribute defaults.

Example:

```bash
kbuild --kbuild-init
```

### `--build-list`

Scans and prints existing version directories in both core and demo trees.

### `--clean`

Prints only the clean option group and exits with success. Must run alone.

### `--clean <name>`

Removes the specified build slot from both core and demos.

### `--clean-latest`

Deletes every `latest` slot in core and demos.

### `--clean-all`

Deletes every build slot in both core and demo trees.

### `--build <name>`

Selects the build slot name. With no version argument, prints only the build
option group and exits with success.

### `--build-latest`

Builds the `latest` slot explicitly.

### `--build-demos [demo ...]`

Builds demos after core SDK build succeeds.

Behavior:

- If demo names are provided, those demos are built in the provided order.
- If no demo names are provided, it uses `build.demos` from the effective
  config.
- Demo tokens are normalized so `exe/core` and `demo/exe/core` both resolve.
- Requires `cmake.sdk.package_name` to be present.
- If the effective config has a `vcpkg` section, demos inherit the same vcpkg
  installed tree/triplet as the core build.

### `--cmake`

Prints only the CMake option group and exits with success. Must run alone.

### `--cmake-configure`

Forces CMake configure before build, overriding `cmake.configure_by_default`
for the current run.

### `--cmake-no-configure`

Skips configure and builds from an existing cache. Requires an existing
`CMakeCache.txt` in the target build directory.

### `--cmake-jobs <n>`

Overrides the parallel job count used for `cmake --build`.

### `--cmake-linkage <t>`

Overrides the configured linkage for the current run. Allowed values are
`static`, `shared`, or `both`.

### `--git`

Prints only the git option group and exits with success. Must run alone.

### `--git-initialize`

Initializes local git repository state and pushes `main` to the configured
remote.

### `--git-sync <msg>`

Runs `git add -A`, commits if needed, and pushes in the repo rooted at the
current directory.

### `--batch [repo ...]`

Runs the remaining command-line args in each target repo, in order.

Behavior:

- With inline repo args, uses those repo paths relative to the current repo
  root.
- With no inline repo args, uses `batch.repos` from the effective config.
- Each target repo must contain `./.kbuild.json`.
- The shared `kbuild` entrypoint is reused for each child repo.

### `--vcpkg`

Prints only the vcpkg option group and exits with success. Must run alone.

### `--vcpkg-sync-baseline`

Reads `./vcpkg/src` HEAD commit hash and writes it into
`vcpkg/vcpkg.json -> configuration.default-registry.baseline`.

### `--vcpkg-install`

Ensures local vcpkg checkout/bootstrap under repo-local `./vcpkg/src`, ensures
local cache directories under `./vcpkg/build`, syncs baseline, then continues
normal build flow.

## 6) Option Combination Rules

`kbuild` enforces mode exclusivity:

- `--kbuild`, `--cmake`, `--git`, and `--vcpkg` are root help commands and must
  be run alone.
- `--kbuild-config` cannot be combined with any other option.
- `--build-list` cannot be combined with other modes.
- `--build` with no version prints only the build option group.
- Clean options cannot be combined with build, git, or init/config options.
- `--clean` with no version prints only the clean option group.
- `--kbuild-init`, `--git-initialize`, `--git-sync`, and
  `--vcpkg-sync-baseline` must run alone.

## 7) Effective Config Schema

### Full schema example

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
  },
  "batch": {
    "repos": [
      "kcli",
      "ktrace"
    ]
  }
}
```

### Required objects

- `project`
- `git`

### Optional objects

- `cmake`
- `vcpkg`
- `build`
- `batch`

### `project`

- `project.title`: required non-empty string
- `project.id`: required C/C++ identifier

### `git`

- `git.url`: required non-empty string
- `git.auth`: required non-empty string

### `cmake`

- `minimum_version`: optional string
- `configure_by_default`: optional boolean, default `true`
- `tests`: optional boolean, default `true`
- `sdk.package_name`: required when `sdk` exists
- `dependencies.<Package>.prefix`: optional dependency map using `{version}`
  token substitution

### `vcpkg`

- `dependencies`: optional array of package names used to generate
  `vcpkg/vcpkg.json`

### `build`

- `jobs`: optional positive integer
- `type`: optional `static`, `shared`, or `both`
- `demos`: optional demo list for `kbuild --build-demos`
- `defaults.demos`: optional demo list auto-built after `kbuild --build-latest`

### `batch`

- `repos`: optional array of relative child-repo paths

## 8) Demo Orchestration

During demo builds, `kbuild` composes `CMAKE_PREFIX_PATH` in this order:

- core SDK prefix: `build/<version>/sdk`
- inherited vcpkg triplet prefix: `build/<version>/installed/<triplet>` when
  `vcpkg` is enabled
- each resolved dependency SDK prefix from `cmake.dependencies`
- any already-built demo SDK prefix for demos earlier in the same order

This means demo order can intentionally represent dependency layering.

## 9) vcpkg Behavior

When `vcpkg` config exists and build mode runs:

- local vcpkg must exist at `./vcpkg/src` and be bootstrapped
- toolchain is forced via the repo-local vcpkg toolchain file
- `VCPKG_ROOT` is set to the local checkout
- repo-local downloads and binary-cache directories are created as needed
- demo builds inherit the same core-build `installed/<triplet>` prefix

`--vcpkg-install` performs initial clone/bootstrap and baseline sync.

## 10) Repo Initialization Details

`--kbuild-init` requires directory hygiene:

- allowed existing entries before run: only `kbuild.json` and `.kbuild.json`
- any extra file or directory triggers a hard error

Generated structure always includes:

- `agent/`, `agent/projects/`
- `cmake/`, `demo/`, `src/`, `tests/`
- root `CMakeLists.txt`, `README.md`, `.gitignore`
- `agent/BOOTSTRAP.md`
- `src/<project_id>.cpp`

If `vcpkg` is defined in the effective config, it also generates:

- `vcpkg/`
- `vcpkg/vcpkg.json`

If `cmake` is defined in the effective config, it also generates:

- `cmake/tests/CMakeLists.txt`
- `cmake/00_toolchain.cmake`
- `cmake/10_dependencies.cmake`
- `cmake/20_targets.cmake`

If `cmake.sdk.package_name` is defined, it also generates SDK/demo packaging
files.

## 11) Common Failure Cases

### `current directory is not a valid kbuild repo root`

Create the primary config first:

```bash
kbuild --kbuild-config
```

### `missing required local config file './.kbuild.json'`

Create the primary config first:

```bash
kbuild --kbuild-config
```

### `--cmake-no-configure requires an existing CMakeCache.txt`

Run with configure once, then retry:

```bash
kbuild --cmake-configure
```

### `demo builds require SDK metadata`

Define `cmake.sdk.package_name` in the effective config.

### `sdk dependency package config not found`

Your `cmake.dependencies.<pkg>.prefix` path is wrong or the dependency SDK is
not built yet. Build the dependency in the same slot and verify
`<prefix>/lib/cmake/<pkg>/<pkg>Config.cmake` exists.

### `vcpkg has not been set up`

Initialize local vcpkg first:

```bash
kbuild --vcpkg-install
```

### `--kbuild-init must be run from an empty directory`

Move existing files out or start in a clean directory containing only
`kbuild.json` and `.kbuild.json`.

### `unexpected key in kbuild config`

The effective config is schema-strict. Remove unknown keys and keep to the
documented key set only.

## 12) Master Command Cheatsheet

Scaffold from zero:

```bash
kbuild --kbuild-config
kbuild --kbuild-init
kbuild --git-initialize
```

Core build + demos:

```bash
kbuild --build-latest
```

Core build in a custom slot:

```bash
kbuild --build dev
```

Install or update local vcpkg then build:

```bash
kbuild --vcpkg-install
```

Sync vcpkg baseline only:

```bash
kbuild --vcpkg-sync-baseline
```

List and clean latest slots:

```bash
kbuild --build-list
kbuild --clean-latest
```
