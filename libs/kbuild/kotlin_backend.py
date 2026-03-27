import os
import re
import shutil
import subprocess

from . import build_ops
from . import config_ops
from . import errors


def is_enabled(repo_root: str) -> bool:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)
    return raw.get("kotlin") is not None


def _load_kotlin_config(repo_root: str) -> tuple[list[str], list[str], str, str, list[tuple[str, str]]]:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)
    kotlin_raw = raw.get("kotlin")
    if not isinstance(kotlin_raw, dict):
        errors.die("kbuild config key 'kotlin' must be an object")

    allowed_kotlin = {"source_roots", "test_roots", "test_main_class", "demo_root", "dependencies"}
    for key in kotlin_raw:
        if key not in allowed_kotlin:
            errors.die(f"unexpected key in kbuild config 'kotlin': '{key}'")

    source_roots = _read_string_list(kotlin_raw.get("source_roots"), key_path="kotlin.source_roots", required=True)
    test_roots = _read_string_list(kotlin_raw.get("test_roots", []), key_path="kotlin.test_roots", required=False)

    test_main_class = kotlin_raw.get("test_main_class", "")
    if test_main_class is None:
        test_main_class = ""
    if not isinstance(test_main_class, str):
        errors.die("kbuild config key 'kotlin.test_main_class' must be a string when defined")

    demo_root = kotlin_raw.get("demo_root", "demo")
    if not isinstance(demo_root, str) or not demo_root.strip():
        errors.die("kbuild config key 'kotlin.demo_root' must be a non-empty string")

    dependency_specs: list[tuple[str, str]] = []
    dependencies_raw = kotlin_raw.get("dependencies", {})
    if not isinstance(dependencies_raw, dict):
        errors.die("kbuild config key 'kotlin.dependencies' must be an object when defined")

    for dependency_name_raw, dependency_raw in dependencies_raw.items():
        if not isinstance(dependency_name_raw, str) or not dependency_name_raw.strip():
            errors.die("kbuild config key 'kotlin.dependencies' has an invalid dependency name")
        dependency_name = dependency_name_raw.strip()
        if not isinstance(dependency_raw, dict):
            errors.die(f"kbuild config key 'kotlin.dependencies.{dependency_name}' must be an object")

        allowed_dependency = {"classes"}
        for key in dependency_raw:
            if key not in allowed_dependency:
                errors.die(f"unexpected key in kbuild config 'kotlin.dependencies.{dependency_name}': '{key}'")

        classes_raw = dependency_raw.get("classes")
        if not isinstance(classes_raw, str) or not classes_raw.strip():
            errors.die(
                f"kbuild config key 'kotlin.dependencies.{dependency_name}.classes' must be a non-empty string"
            )
        dependency_specs.append((dependency_name, classes_raw.strip()))

    return (
        source_roots,
        test_roots,
        test_main_class.strip(),
        demo_root.strip().replace("\\", "/"),
        dependency_specs,
    )


def _read_string_list(value: object, *, key_path: str, required: bool) -> list[str]:
    if value is None:
        if required:
            errors.die(f"kbuild config key '{key_path}' must be an array")
        return []
    if not isinstance(value, list):
        errors.die(f"kbuild config key '{key_path}' must be an array")
    output: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.die(f"kbuild config key '{key_path}[{idx}]' must be a non-empty string")
        output.append(item.strip())
    if required and not output:
        errors.die(f"kbuild config key '{key_path}' must not be empty")
    return output


def _collect_kotlin_files(repo_root: str, roots: list[str]) -> list[str]:
    output: list[str] = []
    for root_token in roots:
        root_path = os.path.join(repo_root, root_token)
        if not os.path.isdir(root_path):
            errors.die(f"kotlin source root does not exist: {root_path}")
        for current_root, _, filenames in os.walk(root_path):
            filenames.sort()
            for filename in filenames:
                if filename.endswith(".kt"):
                    output.append(os.path.join(current_root, filename))
    if not output:
        errors.die("no Kotlin source files found in configured source roots")
    return output


def _prepare_dir(path: str) -> None:
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def _resolve_kotlinc() -> str:
    kotlinc = shutil.which("kotlinc")
    if kotlinc is None:
        return ""
    return os.path.abspath(kotlinc)


def _resolve_java() -> str:
    java = shutil.which("java")
    if java is None:
        errors.die(
            "could not find 'java' on PATH.\n"
            "Install a JRE/JDK or add it to PATH before using the Kotlin backend."
        )
    return os.path.abspath(java)


def _iter_kotlin_lib_dirs(kotlinc: str) -> list[str]:
    candidates: list[str] = []

    kotlin_home = os.environ.get("KOTLIN_HOME", "").strip()
    if kotlin_home:
        candidates.extend(
            [
                os.path.join(kotlin_home, "lib"),
                kotlin_home,
            ]
        )

    if kotlinc:
        candidates.extend(
            [
                os.path.join(os.path.dirname(kotlinc), "..", "lib"),
                os.path.join(os.path.dirname(kotlinc), "..", "..", "lib"),
            ]
        )

    candidates.extend(
        [
            "/snap/kotlin/current/lib",
            "/usr/share/kotlin/kotlinc/lib",
            "/usr/lib/kotlin/lib",
            "/usr/local/lib/kotlin/lib",
            "/opt/kotlinc/lib",
        ]
    )

    output: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = os.path.abspath(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.isdir(normalized):
            output.append(normalized)
    return output


def _resolve_kotlin_compiler_command() -> list[str]:
    kotlinc = _resolve_kotlinc()
    if kotlinc and not kotlinc.startswith("/snap/bin/"):
        return [kotlinc]

    for lib_dir in _iter_kotlin_lib_dirs(kotlinc):
        compiler_jar = os.path.join(lib_dir, "kotlin-compiler.jar")
        if os.path.isfile(compiler_jar):
            java = _resolve_java()
            return [java, "-cp", compiler_jar, "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler"]

    if kotlinc:
        return [kotlinc]

    errors.die(
        "could not find a usable Kotlin compiler.\n"
        "Install the Kotlin compiler or set KOTLIN_HOME before using the Kotlin backend."
    )
    return []


def _compile_kotlin(source_files: list[str], *, out_dir: str, classpath: list[str] | None = None) -> None:
    cmd = _resolve_kotlin_compiler_command()
    cmd.extend(["-d", out_dir])
    if classpath:
        cmd.extend(["-cp", os.pathsep.join(classpath)])
    cmd.extend(source_files)
    subprocess.run(cmd, check=True)


def _resolve_kotlin_dependency_classpath(
    repo_root: str,
    version: str,
    dependency_specs: list[tuple[str, str]],
) -> list[str]:
    resolved: list[str] = []
    for dependency_name, classes_template in dependency_specs:
        raw_path = classes_template.replace("{version}", version)
        candidate_path = os.path.abspath(os.path.join(repo_root, raw_path))
        if not os.path.isdir(candidate_path):
            errors.die(
                "Kotlin dependency classes directory does not exist.\n"
                f"Dependency: {dependency_name}\n"
                f"Expected:\n  {candidate_path}\n"
                "Build the dependency repo first for the same slot."
            )
        resolved.append(candidate_path)
    return resolved


def _find_main_class(source_dir: str) -> str | None:
    source_root = os.path.join(source_dir, "src")
    if not os.path.isdir(source_root):
        return None

    for current_root, _, filenames in os.walk(source_root):
        for filename in sorted(filenames):
            if filename != "Main.kt":
                continue
            main_path = os.path.join(current_root, filename)
            try:
                with open(main_path, "r", encoding="utf-8") as handle:
                    text = handle.read()
            except OSError as exc:
                errors.die(f"could not read demo main source: {main_path}: {exc}")
            match = re.search(r"^\s*package\s+([A-Za-z0-9_.]+)\s*$", text, flags=re.MULTILINE)
            if match:
                return f"{match.group(1)}.Main"
            return "Main"

    return None


def _write_launcher(path: str, *, classpath: list[str], main_class: str) -> None:
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    joined_classpath = os.pathsep.join(classpath)
    payload = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'base_classpath="{joined_classpath}"\n'
        "find_kotlin_lib_dir() {\n"
        '  candidates=()\n'
        '  if [ -n "${KOTLIN_HOME:-}" ]; then\n'
        '    candidates+=("$KOTLIN_HOME/lib" "$KOTLIN_HOME")\n'
        "  fi\n"
        '  if command -v kotlinc >/dev/null 2>&1; then\n'
        '    kotlinc_bin="$(command -v kotlinc)"\n'
        '    candidates+=("$(dirname "$kotlinc_bin")/../lib" "$(dirname "$kotlinc_bin")/../../lib")\n'
        "  fi\n"
        '  candidates+=("/snap/kotlin/current/lib" "/usr/share/kotlin/kotlinc/lib" "/usr/lib/kotlin/lib" "/usr/local/lib/kotlin/lib" "/opt/kotlinc/lib")\n'
        '  for candidate in "${candidates[@]}"; do\n'
        '    if [ -f "$candidate/kotlin-stdlib.jar" ]; then\n'
        '      printf "%s\\n" "$candidate"\n'
        "      return 0\n"
        "    fi\n"
        "  done\n"
        "  return 1\n"
        "}\n"
        'kotlin_lib_dir="$(find_kotlin_lib_dir || true)"\n'
        'runtime_entries=()\n'
        'if [ -n "$kotlin_lib_dir" ]; then\n'
        '  for jar in "$kotlin_lib_dir"/kotlin-stdlib*.jar "$kotlin_lib_dir"/kotlin-reflect*.jar; do\n'
        '    if [ -f "$jar" ]; then\n'
        '      runtime_entries+=("$jar")\n'
        "    fi\n"
        "  done\n"
        "fi\n"
        'runtime_classpath=""\n'
        'if [ "${#runtime_entries[@]}" -gt 0 ]; then\n'
        '  runtime_classpath="${runtime_entries[0]}"\n'
        '  for ((i=1; i<${#runtime_entries[@]}; ++i)); do\n'
        f'    runtime_classpath="$runtime_classpath{os.pathsep}${{runtime_entries[$i]}}"\n'
        "  done\n"
        "fi\n"
        'if [ -n "$runtime_classpath" ]; then\n'
        f'  exec java -cp "$base_classpath{os.pathsep}$runtime_classpath" {main_class} "$@"\n'
        "fi\n"
        'if command -v kotlin >/dev/null 2>&1; then\n'
        f'  exec kotlin -cp "$base_classpath" {main_class} "$@"\n'
        "fi\n"
        'echo "kotlin runtime is unavailable; install kotlin/kotlinc or set KOTLIN_HOME" >&2\n'
        "exit 1\n"
    )
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    os.chmod(path, 0o755)


def build_repo(
    *,
    repo_root: str,
    version: str,
    build_demos: bool,
    requested_demos: list[str],
    config_build_demos: list[str],
    config_default_build_demos: list[str],
) -> int:
    source_roots, test_roots, test_main_class, demo_root, dependency_specs = _load_kotlin_config(repo_root)
    dependency_classpath = _resolve_kotlin_dependency_classpath(repo_root, version, dependency_specs)
    tests_build_dir = ""
    test_launcher_path = ""

    demo_order: list[str] = []
    if build_demos:
        if requested_demos:
            demo_order = [build_ops.normalize_demo_name(token) for token in requested_demos]
        else:
            if not config_build_demos:
                errors.die("config must define 'build.demos' for --build-demos with no demo arguments")
            demo_order = [build_ops.normalize_demo_name(token) for token in config_build_demos]
    elif config_default_build_demos:
        demo_order = [build_ops.normalize_demo_name(token) for token in config_default_build_demos]

    build_dir = os.path.join(repo_root, "build", version)
    sdk_dir = os.path.join(build_dir, "sdk")
    sdk_classes_dir = os.path.join(sdk_dir, "classes")
    _prepare_dir(sdk_classes_dir)

    core_sources = _collect_kotlin_files(repo_root, source_roots)
    _compile_kotlin(core_sources, out_dir=sdk_classes_dir, classpath=dependency_classpath or None)

    if test_roots:
        test_sources = _collect_kotlin_files(repo_root, test_roots)
        tests_build_dir = os.path.join(build_dir, "tests", "classes")
        _prepare_dir(tests_build_dir)
        _compile_kotlin(
            test_sources,
            out_dir=tests_build_dir,
            classpath=[sdk_classes_dir, *dependency_classpath],
        )
        if test_main_class:
            test_launcher_path = os.path.join(build_dir, "tests", "run-tests")

    print(f"Build complete -> dir=build/{version} | sdk={sdk_dir}")

    if not demo_order:
        if test_launcher_path:
            _write_launcher(
                test_launcher_path,
                classpath=[tests_build_dir, sdk_classes_dir, *dependency_classpath],
                main_class=test_main_class,
            )
        return 0

    all_demo_sources = _collect_kotlin_files(repo_root, [demo_root])
    demo_runtime_classpath: list[str] = []
    for demo_name in demo_order:
        source_dir = os.path.join(repo_root, demo_root, demo_name)
        if not os.path.isdir(source_dir):
            errors.die(f"kotlin demo source directory does not exist: {source_dir}")
        demo_build_dir = os.path.join(repo_root, demo_root, demo_name, "build", version)
        print(f"Demo build -> dir={demo_build_dir} | demo={demo_name} | sdk={sdk_dir}", flush=True)
        if demo_name.startswith("sdk/"):
            demo_sdk_dir = os.path.join(demo_build_dir, "sdk")
            demo_classes_dir = os.path.join(demo_sdk_dir, "classes")
            _prepare_dir(demo_classes_dir)
            _compile_kotlin(
                all_demo_sources,
                out_dir=demo_classes_dir,
                classpath=[sdk_classes_dir, *dependency_classpath],
            )
            print(f"Build complete -> dir={demo_build_dir} | sdk={demo_sdk_dir}")
            continue

        demo_classes_dir = os.path.join(demo_build_dir, "classes")
        _prepare_dir(demo_classes_dir)
        _compile_kotlin(
            all_demo_sources,
            out_dir=demo_classes_dir,
            classpath=[sdk_classes_dir, *dependency_classpath],
        )
        demo_runtime_classpath.append(demo_classes_dir)
        main_class = _find_main_class(source_dir)
        if main_class:
            launcher_name = "bootstrap" if demo_name == "bootstrap" else "test"
            _write_launcher(
                os.path.join(demo_build_dir, launcher_name),
                classpath=[demo_classes_dir, sdk_classes_dir, *dependency_classpath],
                main_class=main_class,
            )
        print(f"Build complete -> dir={demo_build_dir} | sdk=<none>")

    if test_launcher_path:
        _write_launcher(
            test_launcher_path,
            classpath=[tests_build_dir, sdk_classes_dir, *dependency_classpath, *demo_runtime_classpath],
            main_class=test_main_class,
        )

    return 0
