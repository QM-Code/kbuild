# Config Guide

`kbuild` reads up to two JSON files:

- `.kbuild.json`: required project marker and primary config
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
| `cmake` | no | CMake build metadata and SDK export settings |
| `cargo` | no | Rust/Cargo build metadata and demo mapping |
| `java` | no | Java source/test/demo layout |
| `swift` | no | Swift package path and demo product mapping |
| `kotlin` | no | Kotlin source/test/demo layout and classpath dependencies |
| `csharp` | no | C# source/test/demo layout and assembly settings |
| `javascript` | no | JavaScript/Node source snapshot, tests, dependencies, and demo launchers |
| `vcpkg` | no | project-local `vcpkg` manifest dependencies |
| `build` | no | job count, linkage defaults, and demo lists |
| `batch` | no | relative child-target list for `--batch` |

Unknown top-level keys are rejected.
Exactly one backend section may be defined in a project config.

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

If `cmake` is selected as the active backend, `kbuild` uses the CMake flow.

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

## Cargo Settings

`cargo.manifest`

- optional string, default `src/Cargo.toml`

`cargo.package`

- optional string forwarded as `--package`

`cargo.tests`

- optional boolean, default `true`

`cargo.sdk.include`

- optional array of paths copied into `build/<slot>/sdk/`

`cargo.demos`

- optional object keyed by demo name
- each entry must define exactly one of:
  - `bin`
  - `example`
- each entry may also define:
  - `manifest`
  - `package`

## Java Settings

`java.source_roots`

- required non-empty array of Java source directories

`java.test_roots`

- optional array of Java test source directories

`java.test_main_class`

- optional main class used to generate `build/<slot>/tests/run-tests`

`java.demo_root`

- optional string, default `demo/java`

## Swift Settings

`swift.package_path`

- required path to the Swift package root containing `Package.swift`

`swift.demo_package_path`

- optional path to the Swift demo package root containing `Package.swift`
- defaults to `swift.package_path`

`swift.demo_products`

- optional object keyed by demo name
- each demo maps to:
  - `product`
  - `kind` as `library` or `executable`

## Kotlin Settings

`kotlin.source_roots`

- required non-empty array of Kotlin source directories

`kotlin.test_roots`

- optional array of Kotlin test source directories

`kotlin.test_main_class`

- optional main class used to generate `build/<slot>/tests/run-tests`

`kotlin.demo_root`

- optional string, default `demo`

## JavaScript Settings

`javascript.package`

- required non-empty package name used for staged SDK metadata and
  `KTOOLS_JS_SDK_ROOT_*` environment variables

`javascript.sdk_dir`

- required path copied into `build/<slot>/sdk/`
- typically `src`

`javascript.test_globs`

- optional array of project-relative test globs passed to `node --test`
- when present, `kbuild` also writes `build/<slot>/tests/run-tests`

`javascript.dependencies`

- optional object keyed by dependency package name
- each dependency currently supports only:
  - `prefix`
- `{version}` in the prefix is replaced with the active build slot
- each resolved SDK must contain `src/<package>`

`javascript.demos`

- optional object keyed by demo name
- each demo entry currently supports:
  - `entry`
  - `output`
- `entry` is the project-relative Node entry script
- `output` is the generated launcher file name under `demo/<demo>/build/<slot>/`

`kotlin.dependencies`

- optional object keyed by dependency name
- each dependency currently defines `classes`, a classes-directory path template

## C# Settings

`csharp.source_roots`

- required non-empty array of C# source directories

`csharp.test_roots`

- optional array of C# test source directories

`csharp.demo_root`

- optional string, default `demo`

`csharp.assembly_name`

- optional assembly name override for generated projects

`csharp.target_framework`

- optional target framework string, default `net10.0`

`csharp.dependencies`

- optional object keyed by friendly dependency name
- each value is a DLL path template

## Vcpkg Settings

`vcpkg.dependencies`

- optional array of package names written into `vcpkg/vcpkg.json` during
  scaffold generation

If the `vcpkg` object is present, build flow expects project-local setup under:

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
machine-specific or project-local overrides in `.kbuild.json`.

If you do not need that split, define the entire config in `.kbuild.json` and
omit `kbuild.json` entirely.

## Strictness Rules

`kbuild` is deliberately schema-strict.

- unknown keys hard-fail
- wrong JSON types hard-fail
- empty required strings hard-fail
- invalid version-slot-like path values hard-fail

Use [kbuild.md](kbuild.md) for the exhaustive schema and validation rules.
