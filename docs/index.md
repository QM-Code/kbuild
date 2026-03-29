# Kbuild Documentation

`kbuild` is a strict Python build and repo orchestration tool for ktools-style
projects. It handles five related jobs:

- creating and validating repo-local kbuild config
- building core targets into named build slots
- building ordered demo trees against the core SDK and dependency SDKs
- scaffolding and helper operations such as repo initialization, git setup, and
  repo-local `vcpkg`
- batch-forwarding commands into child repos

## Start Here

- [Command guide](commands.md)
- [Config guide](config.md)
- [Swift backend notes](swift_backend.md)
- [Common workflows](workflows.md)
- [Full operator reference](kbuild.md)

## Typical Flow

Fresh directory:

```bash
kbuild --kbuild-config
# edit .kbuild.json
kbuild --kbuild-init
kbuild --vcpkg-install
```

Existing repo:

```bash
kbuild --build-latest
kbuild --build-demos
kbuild --clean-latest
```

`kbuild` selects exactly one backend from the repo config. The shared tree
currently supports:

- `cmake`
- `cargo`
- `java`
- `swift`
- `kotlin`
- `csharp`
- `javascript`

## Core Concepts

`Repo root`

- `kbuild` only runs from a directory containing `./.kbuild.json`.

`Primary config`

- `./.kbuild.json` is the required repo marker and primary config file.

`Optional shared base`

- `./kbuild.json` is optional. When present, `kbuild` deep-merges
  `./.kbuild.json` on top of it.

`Build slots`

- Core builds live under `build/<slot>/`.
- Demo builds live under `demo/<demo>/build/<slot>/`.
- The default slot is `latest`.

`Repo hygiene`

- backend-specific generated artifacts are expected to stay under `build/`
- `kbuild` refuses build and git-sync operations when known residuals appear
  outside those directories
- Python repos are also checked for `__pycache__/`, `*.pyc`, and `*.pyo`
  outside `build/`

`SDK-first demos`

- Root builds install an SDK under `build/<slot>/sdk`.
- Demos consume that SDK, optional dependency SDKs, and optionally earlier demo
  SDK outputs in the requested order.

`Repo-local vcpkg`

- When the effective config defines `vcpkg`, `kbuild` expects a repo-local
  checkout under `./vcpkg/src` and integrates it through CMake manifest mode.

## Which Command Should I Reach For?

- Use `kbuild --build-latest` for the normal build path.
- Use `kbuild --build-demos` when you want explicit demo validation.
- Use `kbuild --cmake-no-configure` only for `cmake` repos when the target build directory
  already contains `CMakeCache.txt`.
- Use `kbuild --vcpkg-install` only for `cmake` repos the first time a repo-local `vcpkg` project is
  prepared.
- Use `kbuild --git-initialize` only once, after scaffold generation and remote
  creation.

## Working References

If you want the code behind the behavior, start with:

- [`kbuild` entry script](../kbuild.py)
- [`libs/kbuild/engine.py`](../libs/kbuild/engine.py)
- [`libs/kbuild/config_ops.py`](../libs/kbuild/config_ops.py)
- [`libs/kbuild/repo_init.py`](../libs/kbuild/repo_init.py)
- [`templates/`](../templates/)

If you want the exhaustive CLI and schema rules, use the
[full operator reference](kbuild.md).
