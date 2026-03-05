# Karma CLI Parsing SDK

Standalone CLI parsing SDK used by `ktrace` and `kconfig`.

## Build SDK

```bash
./kbuild.py
```

SDK output:
- `build/latest/sdk/include`
- `build/latest/sdk/lib`
- `build/latest/sdk/lib/cmake/KcliSDK`

## Build and Test Demos

```bash
# Uses kbuild.json "build.demos" order.
./kbuild.py --build-demos

./demo/executable/build/latest/test
```

Demos:
- Libraries: `demo/libraries/{alpha,beta,gamma}`
- Executable: `demo/executable/`
- Bootstrap compile/link check: `demo/bootstrap/`

Demo builds are orchestrated by the root `kbuild.py`.

Useful demo commands:

```bash
./demo/executable/build/latest/test
./demo/executable/build/latest/test --alpha
./demo/executable/build/latest/test --alpha-message "hello"
./demo/executable/build/latest/test --beta-workers 8
./demo/executable/build/latest/test --renamed-tag "prod"
./demo/executable/build/latest/test --alpha-d
```

## Parser Modes

- End-user mode (default): `Initialize(argc, argv)`  
  Handles top-level options and aliases (for example `-v -> verbose`).
- Inline mode: `Initialize(argc, argv, "root")`  
  Handles `--<root>` and `--<root>-*` only.

Inline mode behavior:
- `--<root>` always prints available `--<root>-*` options.
- `--<root> value [value...]` is accepted only when a root value handler is registered.
- Unknown `--<root>-*` options hard-error.
- Aliases are not allowed.

Root token rules:
- Root must be bare (for example `"trace"`, not `"--trace"`).
- Roots beginning with `-` are rejected.

## Install

Consumer CMake:

```cmake
find_package(KcliSDK CONFIG REQUIRED)
target_link_libraries(main PRIVATE kcli::sdk)
```

## Coding Agents

If you are using a coding agent, paste the following prompt:

```bash
Follow the instructions in agent/BOOTSTRAP.md
```
