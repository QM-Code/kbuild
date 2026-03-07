# Karma Build Script

Standardized build tooling for ktools projects.

## Build

```bash
./kbuild.py
```

## Usage
- Grab the latest git release: https://github.com/QM-Code/kbuild
- Copy `kbuild.py` to an empty directory.
- Run `./kbuild.py --kbuild-root <directory>`.
- Run `./kbuild.py --kbuild-config`.
- Edit `./kbuild.json`.
- Run `./kbuild.py --kbuild-init`.

`<directory>` should be the relative or absolute path to the pulled `kbuild` directory (where you copied `kbuild.py` from).

See `docs/kbuild.md` for full documentation.

## Coding Agents

If you are using a coding agent, start with:

```bash
Follow docs/kbuild.md section "0) Agent Bootstrap Runbook (Read This First)"
```
