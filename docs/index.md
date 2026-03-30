# Kbuild Documentation

`kbuild` is a strict Python build and project orchestration tool for
ktools-style workspaces and components. It handles five related jobs:

- creating and validating project-local kbuild config
- building core targets into named build slots
- building ordered demo trees against the core SDK and dependency SDKs
- scaffolding and helper operations such as project initialization, git setup,
  and project-local `vcpkg`
- batch-forwarding commands into child targets

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

Existing project:

```bash
kbuild --build-latest
kbuild --build-demos
kbuild --clean-latest
```

`kbuild` selects exactly one backend from the project config. The shared tree
currently supports:

- `cmake`
- `cargo`
- `java`
- `swift`
- `kotlin`
- `csharp`
- `javascript`

## Core Concepts

`Project root`

- `kbuild` only runs from a directory containing `./.kbuild.json`.

`Primary config`

- `./.kbuild.json` is the required project marker and primary config file.

`Optional shared base`

- `./kbuild.json` is optional. When present, `kbuild` deep-merges
  `./.kbuild.json` on top of it.

`Build slots`

- Core builds live under `build/<slot>/`.
- Demo builds live under `demo/<demo>/build/<slot>/`.
- The default slot is `latest`.

`Project hygiene`

- backend-specific generated artifacts are expected to stay under `build/`
- `kbuild` refuses build and git-sync operations when known residuals appear
  outside those directories
- for `cmake` projects this includes source-tree configure/build artifacts such as
  `CMakeCache.txt`, `CMakeFiles/`, `build.ninja`, and `cmake_install.cmake`
- Python projects are also checked for `__pycache__/`, `*.pyc`, and `*.pyo`
  outside `build/`

`SDK-first demos`

- Root builds install an SDK under `build/<slot>/sdk`.
- Demos consume that SDK, optional dependency SDKs, and optionally earlier demo
  SDK outputs in the requested order.

`Project-local vcpkg`

- When the effective config defines `vcpkg`, `kbuild` expects a project-local
  checkout under `./vcpkg/src` and integrates it through CMake manifest mode.

## Which Command Should I Reach For?

- Use `kbuild --build-latest` for the normal build path.
- Use `kbuild --build-demos` when you want explicit demo validation.
- Use `kbuild --cmake-no-configure` only for `cmake` projects when the target build directory
  already contains `CMakeCache.txt`.
- Use `kbuild --vcpkg-install` only for `cmake` projects the first time a project-local `vcpkg` checkout is
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
