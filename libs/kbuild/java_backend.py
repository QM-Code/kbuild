import os
import re
import shutil
import subprocess

from . import build_ops
from . import config_ops
from . import errors


def is_enabled(repo_root: str) -> bool:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)
    return raw.get('java') is not None


def _load_java_config(repo_root: str) -> tuple[list[str], list[str], str, str, list[tuple[str, str]]]:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)
    java_raw = raw.get('java')
    if not isinstance(java_raw, dict):
        errors.die("kbuild config key 'java' must be an object")

    allowed_java = {'source_roots', 'test_roots', 'test_main_class', 'demo_root', 'dependencies'}
    for key in java_raw:
        if key not in allowed_java:
            errors.die(f"unexpected key in kbuild config 'java': '{key}'")

    source_roots = _read_string_list(java_raw.get('source_roots'), key_path='java.source_roots', required=True)
    test_roots = _read_string_list(java_raw.get('test_roots', []), key_path='java.test_roots', required=False)

    test_main_class = java_raw.get('test_main_class', '')
    if test_main_class is None:
        test_main_class = ''
    if not isinstance(test_main_class, str):
        errors.die("kbuild config key 'java.test_main_class' must be a string when defined")

    demo_root = java_raw.get('demo_root', 'demo')
    if not isinstance(demo_root, str) or not demo_root.strip():
        errors.die("kbuild config key 'java.demo_root' must be a non-empty string")

    dependency_specs: list[tuple[str, str]] = []
    dependencies_raw = java_raw.get('dependencies', {})
    if not isinstance(dependencies_raw, dict):
        errors.die("kbuild config key 'java.dependencies' must be an object when defined")

    for dependency_name_raw, dependency_raw in dependencies_raw.items():
        if not isinstance(dependency_name_raw, str) or not dependency_name_raw.strip():
            errors.die("kbuild config key 'java.dependencies' has an invalid dependency name")
        dependency_name = dependency_name_raw.strip()
        if not isinstance(dependency_raw, dict):
            errors.die(f"kbuild config key 'java.dependencies.{dependency_name}' must be an object")

        allowed_dependency = {'classes'}
        for key in dependency_raw:
            if key not in allowed_dependency:
                errors.die(
                    f"unexpected key in kbuild config 'java.dependencies.{dependency_name}': '{key}'")

        classes_raw = dependency_raw.get('classes')
        if not isinstance(classes_raw, str) or not classes_raw.strip():
            errors.die(
                f"kbuild config key 'java.dependencies.{dependency_name}.classes' must be a non-empty string")
        dependency_specs.append((dependency_name, classes_raw.strip()))

    return (
        source_roots,
        test_roots,
        test_main_class.strip(),
        demo_root.strip().replace('\\', '/'),
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


def _collect_java_files(repo_root: str, roots: list[str]) -> list[str]:
    output: list[str] = []
    for root_token in roots:
        root_path = os.path.join(repo_root, root_token)
        if not os.path.isdir(root_path):
            errors.die(f"java source root does not exist: {root_path}")
        for current_root, _, filenames in os.walk(root_path):
            filenames.sort()
            for filename in filenames:
                if filename.endswith('.java'):
                    output.append(os.path.join(current_root, filename))
    if not output:
        errors.die('no Java source files found in configured source roots')
    return output


def _prepare_dir(path: str) -> None:
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def _compile_java(source_files: list[str], *, out_dir: str, classpath: list[str] | None = None) -> None:
    cmd = ['javac', '-d', out_dir]
    if classpath:
        cmd.extend(['-cp', os.pathsep.join(classpath)])
    cmd.extend(source_files)
    subprocess.run(cmd, check=True)


def _resolve_java_dependency_classpath(
    repo_root: str,
    version: str,
    dependency_specs: list[tuple[str, str]],
) -> list[str]:
    resolved: list[str] = []
    for dependency_name, classes_template in dependency_specs:
        raw_path = classes_template.replace('{version}', version)
        candidate_path = os.path.abspath(os.path.join(repo_root, raw_path))
        if not os.path.isdir(candidate_path):
            errors.die(
                "Java dependency classes directory does not exist.\n"
                f"Dependency: {dependency_name}\n"
                f"Expected:\n  {candidate_path}\n"
                "Build the dependency repo first for the same slot."
            )
        resolved.append(candidate_path)
    return resolved


def _find_main_class(source_dir: str) -> str | None:
    source_root = os.path.join(source_dir, 'src')
    if not os.path.isdir(source_root):
        return None

    for current_root, _, filenames in os.walk(source_root):
        for filename in sorted(filenames):
            if filename != 'Main.java':
                continue
            main_path = os.path.join(current_root, filename)
            try:
                with open(main_path, 'r', encoding='utf-8') as handle:
                    text = handle.read()
            except OSError as exc:
                errors.die(f"could not read demo main source: {main_path}: {exc}")
            match = re.search(r'^\s*package\s+([A-Za-z0-9_.]+)\s*;', text, flags=re.MULTILINE)
            if match:
                return f"{match.group(1)}.Main"
            return 'Main'

    return None


def _write_launcher(path: str, *, classpath: list[str], main_class: str) -> None:
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    payload = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'exec java -cp "{os.pathsep.join(classpath)}" {main_class} "$@"\n'
    )
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
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
    source_roots, test_roots, test_main_class, demo_root, dependency_specs = _load_java_config(repo_root)
    dependency_classpath = _resolve_java_dependency_classpath(repo_root, version, dependency_specs)
    tests_build_dir = ''
    test_launcher_path = ''

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

    build_dir = os.path.join(repo_root, 'build', version)
    sdk_dir = os.path.join(build_dir, 'sdk')
    sdk_classes_dir = os.path.join(sdk_dir, 'classes')
    _prepare_dir(sdk_classes_dir)

    core_sources = _collect_java_files(repo_root, source_roots)
    _compile_java(core_sources, out_dir=sdk_classes_dir, classpath=dependency_classpath or None)

    if test_roots:
        test_sources = _collect_java_files(repo_root, test_roots)
        tests_build_dir = os.path.join(build_dir, 'tests', 'classes')
        _prepare_dir(tests_build_dir)
        _compile_java(
            test_sources,
            out_dir=tests_build_dir,
            classpath=[sdk_classes_dir, *dependency_classpath],
        )
        if test_main_class:
            test_launcher_path = os.path.join(build_dir, 'tests', 'run-tests')

    print(f"Build complete -> dir=build/{version} | sdk={sdk_dir}")

    if not demo_order:
        if test_launcher_path:
            _write_launcher(
                test_launcher_path,
                classpath=[tests_build_dir, sdk_classes_dir, *dependency_classpath],
                main_class=test_main_class,
            )
        return 0

    all_demo_sources = _collect_java_files(repo_root, [demo_root])
    demo_runtime_classpath: list[str] = []
    for demo_name in demo_order:
        source_dir = os.path.join(repo_root, demo_root, demo_name)
        if not os.path.isdir(source_dir):
            errors.die(f"java demo source directory does not exist: {source_dir}")
        demo_build_dir = os.path.join(repo_root, demo_root, demo_name, 'build', version)
        print(f"Demo build -> dir={demo_build_dir} | demo={demo_name} | sdk={sdk_dir}", flush=True)
        if demo_name.startswith('sdk/'):
            demo_sdk_dir = os.path.join(demo_build_dir, 'sdk')
            demo_classes_dir = os.path.join(demo_sdk_dir, 'classes')
            _prepare_dir(demo_classes_dir)
            _compile_java(
                all_demo_sources,
                out_dir=demo_classes_dir,
                classpath=[sdk_classes_dir, *dependency_classpath],
            )
            print(f"Build complete -> dir={demo_build_dir} | sdk={demo_sdk_dir}")
            continue

        demo_classes_dir = os.path.join(demo_build_dir, 'classes')
        _prepare_dir(demo_classes_dir)
        _compile_java(
            all_demo_sources,
            out_dir=demo_classes_dir,
            classpath=[sdk_classes_dir, *dependency_classpath],
        )
        demo_runtime_classpath.append(demo_classes_dir)
        main_class = _find_main_class(source_dir)
        if main_class:
            launcher_name = 'bootstrap' if demo_name == 'bootstrap' else 'test'
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
