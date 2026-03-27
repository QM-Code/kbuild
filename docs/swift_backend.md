# Swift Backend Notes

This shared `kbuild` tree includes a SwiftPM backend used by the
`ktools-swift/` workspace.

## Current Model

For repos with a `swift` config block:

- core package build output lives under `build/<slot>/swiftpm/`
- SDK output is a source snapshot under `build/<slot>/sdk/`
- tests get a launcher at `build/<slot>/tests/run-tests`
- executable demos get launchers under `demo/<demo>/build/<slot>/`
- library demos get a source snapshot under `demo/<demo>/build/<slot>/sdk/`

## Local Swift State

The shared backend keeps SwiftPM cache and config state inside the active build
slot rather than spilling into user-global cache directories. Each build creates
local state under:

- `build/<slot>/_swift/cache`
- `build/<slot>/_swift/config`
- `build/<slot>/_swift/security`
- `build/<slot>/_swift/xdg-cache`
- `build/<slot>/_swift/clang-module-cache`
- `build/<slot>/_swift/prebuilt-module-cache`

Generated test and demo launchers also reuse those local paths so repeated runs
stay aligned with the original build.

## Swiftly Integration

If Swiftly is installed, generated launchers source:

- `${SWIFTLY_HOME_DIR:-$HOME/.local/share/swiftly}/env.sh`

before invoking `swift run` or `swift test`. That keeps the launcher behavior
consistent with interactive Swiftly-managed environments.
