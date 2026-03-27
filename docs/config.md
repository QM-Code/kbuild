# Config Guide

`kbuild` reads up to two JSON files:

- `.kbuild.json`: required repo marker and primary config
- `kbuild.json`: optional shared base config

At runtime, `kbuild` deep-merges `.kbuild.json` on top of `kbuild.json` when
both files exist.

## Primary Config

Starter config:

```bash
kbuild --kbuild-config
```

This creates `./.kbuild.json`.

Representative full example:

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
    "tests": true,
    "sdk": {
      "package_name": "ExampleProjectSDK"
    },
    "dependencies": {
      "KcliSDK": {
        "prefix": "../kcli/build/{version}/sdk"
      }
    }
  },
  "vcpkg": {
    "dependencies": [
      "fmt",
      "spdlog"
    ]
  },
  "build": {
    "jobs": 4,
    "type": "shared",
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

## Top-Level Keys

| Key | Required | Purpose |
| --- | --- | --- |
| `project` | yes | human title plus stable project identifier |
| `git` | yes | remote URLs used by git helper modes |
| `cmake` | no | build-system metadata and SDK export settings |
| `vcpkg` | no | repo-local `vcpkg` manifest dependencies |
| `build` | no | job count, linkage defaults, and demo lists |
| `batch` | no | relative child-repo list for `--batch` |

Unknown top-level keys are rejected.

## Project Settings

`project.title`

- required non-empty string used in generated text

`project.id`

- required non-empty C/C++ identifier
- used in generated filenames, namespaces, and target variables

## Git Settings

`git.url`

- required non-empty string
- used as the canonical browser/display URL for the repository

`git.auth`

- required non-empty string
- used for authenticated remote operations and git preflight checks

## CMake Settings

If `cmake` is omitted, normal build mode validates config and returns
`Nothing to do.`

`cmake.minimum_version`

- optional string for generated `CMakeLists.txt`

`cmake.configure_by_default`

- optional boolean, default `true`

`cmake.tests`

- optional boolean, default `true`

`cmake.sdk.package_name`

- required when `cmake.sdk` exists
- enables SDK packaging and demo package resolution

`cmake.dependencies`

- optional object keyed by dependency package name
- each dependency currently supports only `prefix`
- `{version}` in the prefix is replaced with the active build slot

Dependency prefixes are validated before build use. `kbuild` expects each
prefix to contain:

- `include/`
- `lib/`
- `lib/cmake/<Package>/<Package>Config.cmake`

## Vcpkg Settings

`vcpkg.dependencies`

- optional array of package names written into `vcpkg/vcpkg.json` during
  scaffold generation

If the `vcpkg` object is present, build flow expects repo-local setup under:

- `vcpkg/src`
- `vcpkg/build`

## Build Settings

`build.jobs`

- optional positive integer

`build.type`

- optional linkage default
- one of `static`, `shared`, or `both`

`build.demos`

- optional list used by `kbuild --build-demos` when no demo names are passed

`build.defaults.demos`

- optional list auto-built after `kbuild --build-latest`

## Local Overlay Behavior

If you want a shared committed base config, keep it in `kbuild.json` and put
machine-specific or repo-local overrides in `.kbuild.json`.

If you do not need that split, define the entire config in `.kbuild.json` and
omit `kbuild.json` entirely.

## Strictness Rules

`kbuild` is deliberately schema-strict.

- unknown keys hard-fail
- wrong JSON types hard-fail
- empty required strings hard-fail
- invalid version-slot-like path values hard-fail

Use [kbuild.md](kbuild.md) for the exhaustive schema and validation rules.
