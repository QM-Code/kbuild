# Common Workflows

This page collects the normal operating sequences for `kbuild`.

## Empty Directory To Scaffolded Repo

1. Create starter config in the empty directory.
2. Edit the config.
3. Scaffold the repo.
4. Initialize git if needed.
5. Install local `vcpkg` if the repo uses it.

```bash
kbuild --kbuild-config
# edit ./.kbuild.json
kbuild --kbuild-init
kbuild --git-initialize
kbuild --vcpkg-install
```

Notes:

- `--kbuild-init` requires the directory to be otherwise empty except for
  `kbuild.json` and `.kbuild.json`.
- scaffolded SDK repos include core CMake files, demo trees, test placeholders,
  and optional `vcpkg/vcpkg.json`.

## Existing Repo Day-To-Day

Normal build:

```bash
kbuild --build-latest
```

Fast rebuild from an existing cache:

```bash
kbuild --build-latest --cmake-no-configure
kbuild --build-demos --cmake-no-configure
```

Fresh rebuild:

```bash
kbuild --clean-latest
kbuild --build-latest
```

## Explicit Demo Validation

Build demos from config order:

```bash
kbuild --build-demos
```

Build an explicit chain:

```bash
kbuild --build dev --build-demos sdk/alpha sdk/beta exe/core
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
kbuild --build dev

cd ../ktrace
kbuild --build dev --vcpkg-install

cd ../myproject
kbuild --build dev --vcpkg-install
kbuild --build dev --build-demos
```

This works cleanly when `cmake.dependencies` uses version-aware prefixes such
as:

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
kbuild --git-initialize
```

For later full syncs:

```bash
kbuild --git-sync "Update project docs"
```

`kbuild` refuses to use a parent git worktree for sync operations. The repo
must be rooted at the current directory.

## Vcpkg Bring-Up

For repos that define a `vcpkg` object:

```bash
kbuild --vcpkg-install
```

This prepares:

- `vcpkg/src`
- `vcpkg/build/downloads`
- `vcpkg/build/binary-cache`

If you only need to update the manifest baseline from the checked-out vcpkg
commit:

```bash
kbuild --vcpkg-sync-baseline
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
kbuild --build-latest --cmake-configure
```

For the exhaustive command semantics and failure cases, see
[kbuild.md](kbuild.md).
