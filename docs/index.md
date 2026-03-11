# Kbuild Documentation

`kbuild` is a strict Python build and repo orchestration tool for ktools-style
CMake projects. It handles five related jobs:

- bootstrapping a thin `kbuild.py` wrapper against a shared `kbuild` checkout
- validating and loading `kbuild.json`
- building core targets into named build slots
- building ordered demo trees against the core SDK and dependency SDKs
- scaffolding and helper operations such as repo initialization, git setup, and
  repo-local `vcpkg`

## Start Here

- [Command guide](commands.md)
- [Config guide](config.md)
- [Common workflows](workflows.md)
- [Full operator reference](kbuild.md)

## Typical Flow

Fresh directory:

```bash
./kbuild.py --kbuild-root /path/to/kbuild
./kbuild.py --kbuild-config
# edit kbuild.json
./kbuild.py --kbuild-init
./kbuild.py --vcpkg-install
```

Existing repo:

```bash
./kbuild.py --build-latest
./kbuild.py --build-demos
./kbuild.py --clean-latest
```

## Core Concepts

`Shared root`

- The copied wrapper `kbuild.py` loads the implementation from a shared
  checkout recorded in `./.kbuild.json -> kbuild.root`.

`Shared config`

- `kbuild.json` is the committed project config. Unknown keys are rejected.

`Local overlay`

- `./.kbuild.json` is primarily used for `kbuild.root` and may also overlay
  local config values for the current machine.

`Build slots`

- Core builds live under `build/<slot>/`.
- Demo builds live under `demo/<demo>/build/<slot>/`.
- The default slot is `latest`.

`SDK-first demos`

- Root builds install an SDK under `build/<slot>/sdk`.
- Demos consume that SDK, optional dependency SDKs, and optionally earlier demo
  SDK outputs in the requested order.

`Repo-local vcpkg`

- When `kbuild.json` defines `vcpkg`, `kbuild` expects a repo-local checkout
  under `./vcpkg/src` and integrates it through CMake manifest mode.

## Which Command Should I Reach For?

- Use `./kbuild.py --build-latest` for the normal build path.
- Use `./kbuild.py --build-demos` when you want explicit demo validation.
- Use `./kbuild.py --cmake-no-configure` only when the target build directory
  already contains `CMakeCache.txt`.
- Use `./kbuild.py --vcpkg-install` the first time a repo-local `vcpkg` project
  is prepared.
- Use `./kbuild.py --git-initialize` only once, after scaffold generation and
  remote creation.

## Working References

If you want the code behind the behavior, start with:

- [`kbuild.py`](../kbuild.py)
- [`libs/kbuild/engine.py`](../libs/kbuild/engine.py)
- [`libs/kbuild/config_ops.py`](../libs/kbuild/config_ops.py)
- [`libs/kbuild/repo_init.py`](../libs/kbuild/repo_init.py)
- [`templates/`](../templates/)

If you want the exhaustive CLI and schema rules, use the
[full operator reference](kbuild.md).
