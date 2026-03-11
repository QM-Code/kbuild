# Common Workflows

This page collects the normal operating sequences for `kbuild`.

## Empty Directory To Scaffolded Repo

1. Copy `kbuild.py` into the empty directory.
2. Point the wrapper at the shared `kbuild` checkout.
3. Create `kbuild.json`.
4. Edit the config.
5. Scaffold the repo.
6. Initialize git if needed.
7. Install local `vcpkg` if the repo uses it.

```bash
./kbuild.py --kbuild-root /path/to/kbuild
./kbuild.py --kbuild-config
# edit ./kbuild.json
./kbuild.py --kbuild-init
./kbuild.py --git-initialize
./kbuild.py --vcpkg-install
```

Notes:

- `--kbuild-init` requires the directory to be otherwise empty except for
  `kbuild.py`, `kbuild.json`, and `.kbuild.json`.
- scaffolded SDK repos include core CMake files, demo trees, test placeholders,
  and optional `vcpkg/vcpkg.json`.

## Existing Repo Day-To-Day

Normal build:

```bash
./kbuild.py --build-latest
```

Fast rebuild from an existing cache:

```bash
./kbuild.py --build-latest --cmake-no-configure
./kbuild.py --build-demos --cmake-no-configure
```

Fresh rebuild:

```bash
./kbuild.py --clean-latest
./kbuild.py --build-latest
```

## Explicit Demo Validation

Build demos from config order:

```bash
./kbuild.py --build-demos
```

Build an explicit chain:

```bash
./kbuild.py --build dev --build-demos sdk/alpha sdk/beta exe/core
```

Why order matters:

- demos can consume the core SDK install under `build/<slot>/sdk`
- demos can consume SDK dependencies from `cmake.dependencies`
- later demos can consume SDKs installed by earlier demos in the same run

## Multi-Repo SDK Stack

Use one shared slot name across the related repos, then build dependencies
before consumers.

Example:

```bash
cd ../kcli
./kbuild.py --build dev

cd ../ktrace
./kbuild.py --build dev --vcpkg-install

cd ../myproject
./kbuild.py --build dev --vcpkg-install
./kbuild.py --build dev --build-demos
```

This works cleanly when `cmake.dependencies` uses version-aware prefixes such as:

```json
"dependencies": {
  "KcliSDK": {
    "prefix": "../kcli/build/{version}/sdk"
  },
  "KTraceSDK": {
    "prefix": "../ktrace/build/{version}/sdk"
  }
}
```

## Git Bring-Up

After scaffold generation and remote creation:

```bash
./kbuild.py --git-initialize
```

For later full syncs:

```bash
./kbuild.py --git-sync "Update project docs"
```

`kbuild` refuses to use a parent git worktree for sync operations. The repo must
be rooted at the current directory.

## Vcpkg Bring-Up

For repos that define a `vcpkg` object:

```bash
./kbuild.py --vcpkg-install
```

This prepares:

- `vcpkg/src`
- `vcpkg/build/downloads`
- `vcpkg/build/binary-cache`

If you only need to update the manifest baseline from the checked-out vcpkg
commit:

```bash
./kbuild.py --vcpkg-sync-baseline
```

## When To Stop And Reconfigure

Run a configure pass again when:

- toolchain settings changed
- dependency prefixes changed
- `vcpkg` state changed
- linkage mode changed
- you cleaned the build slot

Use:

```bash
./kbuild.py --build-latest --cmake-configure
```

For the exhaustive command semantics and failure cases, see
[kbuild.md](kbuild.md).
