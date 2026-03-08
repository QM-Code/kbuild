# Karma Build Script

Standardized build tooling for ktools projects.

## Help

```bash
./kbuild.py --help
```

Running `./kbuild.py` with no arguments also prints usage. It does not build.

## Quick Start
- Grab the latest git release: https://github.com/QM-Code/kbuild
- Copy `kbuild.py` to an empty directory.
- Run `./kbuild.py --kbuild-root <directory>`.
- Run `./kbuild.py --kbuild-config`.
- Edit `./kbuild.json`.
- Run `./kbuild.py --kbuild-init`.

## Common Build Commands

```bash
./kbuild.py --build-latest
./kbuild.py --build-demos
./kbuild.py --clean-latest
```

`<directory>` should be the relative or absolute path to the pulled `kbuild` directory (where you copied `kbuild.py` from).

See `docs/kbuild.md` for full documentation.

## Coding Agents

If you are using a coding agent, start with:

```bash
Follow docs/kbuild.md section "0) Agent Bootstrap Runbook (Read This First)"
```
