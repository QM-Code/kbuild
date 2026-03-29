import os
import shutil
import subprocess
import textwrap
import xml.sax.saxutils as xml_utils
from dataclasses import dataclass

from . import build_ops
from . import config_ops
from . import errors


_RESIDUAL_DIR_NAMES = {
    "bin",
    "obj",
    "TestResults",
}

_RESIDUAL_FILE_NAMES = {
    "project.assets.json",
}

_RESIDUAL_FILE_SUFFIXES = (
    ".deps.json",
    ".runtimeconfig.json",
    ".runtimeconfig.dev.json",
    ".sourcelink.json",
    ".nuget.dgspec.json",
    ".nuget.g.props",
    ".nuget.g.targets",
)


def is_enabled(repo_root: str) -> bool:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)
    return raw.get("csharp") is not None


def find_unexpected_residuals(repo_root: str) -> tuple[str, list[str]] | None:
    findings: list[str] = []
    for current_root, dirnames, filenames in os.walk(repo_root):
        unexpected_dirs = []
        kept_dirnames = []
        for dirname in sorted(dirnames):
            if dirname in (".git", "build"):
                continue
            if dirname in _RESIDUAL_DIR_NAMES:
                unexpected_dirs.append(os.path.join(current_root, dirname))
                continue
            kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames
        findings.extend(unexpected_dirs)

        for filename in sorted(filenames):
            if filename in _RESIDUAL_FILE_NAMES:
                findings.append(os.path.join(current_root, filename))
                continue
            if filename.endswith(_RESIDUAL_FILE_SUFFIXES):
                findings.append(os.path.join(current_root, filename))

    if not findings:
        return None
    return ("C# build residuals", findings)


def _load_csharp_config(
    repo_root: str,
) -> tuple[str, list[str], list[str], str, str, dict[str, str]]:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)

    project_raw = raw.get("project")
    if not isinstance(project_raw, dict):
        errors.die("kbuild config key 'project' must be an object")
    project_id_raw = project_raw.get("id")
    if not isinstance(project_id_raw, str) or not project_id_raw.strip():
        errors.die("kbuild config key 'project.id' must be a non-empty string")

    csharp_raw = raw.get("csharp")
    if not isinstance(csharp_raw, dict):
        errors.die("kbuild config key 'csharp' must be an object")

    allowed_csharp = {
        "source_roots",
        "test_roots",
        "demo_root",
        "assembly_name",
        "target_framework",
        "dependencies",
    }
    for key in csharp_raw:
        if key not in allowed_csharp:
            errors.die(f"unexpected key in kbuild config 'csharp': '{key}'")

    source_roots = _read_string_list(
        csharp_raw.get("source_roots"),
        key_path="csharp.source_roots",
        required=True,
    )
    test_roots = _read_string_list(
        csharp_raw.get("test_roots", []),
        key_path="csharp.test_roots",
        required=False,
    )

    demo_root_raw = csharp_raw.get("demo_root", "demo")
    if not isinstance(demo_root_raw, str) or not demo_root_raw.strip():
        errors.die("kbuild config key 'csharp.demo_root' must be a non-empty string")
    demo_root = demo_root_raw.strip().replace("\\", "/")

    assembly_name_raw = csharp_raw.get("assembly_name", "")
    if assembly_name_raw is None:
        assembly_name_raw = ""
    if not isinstance(assembly_name_raw, str):
        errors.die("kbuild config key 'csharp.assembly_name' must be a string when defined")
    assembly_name = assembly_name_raw.strip() or _pascalize_identifier(project_id_raw.strip())

    target_framework_raw = csharp_raw.get("target_framework", "net10.0")
    if not isinstance(target_framework_raw, str) or not target_framework_raw.strip():
        errors.die("kbuild config key 'csharp.target_framework' must be a non-empty string")
    target_framework = target_framework_raw.strip()

    dependencies_raw = csharp_raw.get("dependencies", {})
    if not isinstance(dependencies_raw, dict):
        errors.die("kbuild config key 'csharp.dependencies' must be an object when defined")
    dependencies: dict[str, str] = {}
    for dependency_name_raw, path_raw in dependencies_raw.items():
        if not isinstance(dependency_name_raw, str) or not dependency_name_raw.strip():
            errors.die("kbuild config key 'csharp.dependencies' has an invalid dependency name")
        if not isinstance(path_raw, str) or not path_raw.strip():
            errors.die(
                f"kbuild config key 'csharp.dependencies.{dependency_name_raw}' must be a non-empty string"
            )
        dependencies[dependency_name_raw.strip()] = path_raw.strip()

    return assembly_name, source_roots, test_roots, demo_root, target_framework, dependencies


def _pascalize_identifier(value: str) -> str:
    parts = [part for part in value.replace("-", "_").split("_") if part]
    if not parts:
        return "Project"
    return "".join(part[:1].upper() + part[1:] for part in parts)


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


def _collect_csharp_files(repo_root: str, roots: list[str]) -> list[str]:
    output: list[str] = []
    for root_token in roots:
        root_path = os.path.join(repo_root, root_token)
        if not os.path.isdir(root_path):
            errors.die(f"csharp source root does not exist: {root_path}")
        for current_root, _, filenames in os.walk(root_path):
            filenames.sort()
            for filename in filenames:
                if filename.endswith(".cs"):
                    output.append(os.path.join(current_root, filename))
    if roots and not output:
        errors.die("no C# source files found in configured source roots")
    return output


def _prepare_dir(path: str) -> None:
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def _ensure_dotnet() -> str:
    dotnet = shutil.which("dotnet")
    if dotnet:
        return dotnet
    errors.die(
        "C# backend requires the 'dotnet' CLI on PATH.\n"
        "Install a supported .NET SDK or run on a machine where 'dotnet' is available."
    )


def _resolve_dependency_references(
    *,
    repo_root: str,
    version: str,
    dependency_templates: dict[str, str],
) -> list[tuple[str, str]]:
    resolved: list[tuple[str, str]] = []
    for dependency_name, path_template in dependency_templates.items():
        raw_path = path_template.replace("{version}", version)
        candidate_path = build_ops.resolve_prefix(raw_path, repo_root)
        if not os.path.isfile(candidate_path):
            errors.die(
                "csharp dependency DLL not found.\n"
                f"Dependency:\n  {dependency_name}\n"
                "Checked path:\n"
                f"  {candidate_path}"
            )
        resolved.append((dependency_name, candidate_path))
    return resolved


def _relative_link_label(base_dir: str, path: str) -> str:
    return os.path.relpath(path, base_dir).replace("\\", "/")


@dataclass(frozen=True)
class _GeneratedProjectSpec:
    project_path: str
    assembly_name: str
    target_framework: str
    output_type: str
    output_dir: str
    intermediate_dir: str
    source_files: list[str]
    references: list[tuple[str, str]]


def _write_generated_project(spec: _GeneratedProjectSpec) -> None:
    os.makedirs(os.path.dirname(spec.project_path), exist_ok=True)
    compile_items = "\n".join(
        f'    <Compile Include="{xml_utils.escape(path)}" Link="{xml_utils.escape(_relative_link_label(os.path.dirname(spec.project_path), path))}" />'
        for path in spec.source_files
    )
    reference_items = "\n".join(
        textwrap.dedent(
            f"""\
                <Reference Include="{xml_utils.escape(name)}">
                  <HintPath>{xml_utils.escape(path)}</HintPath>
                  <Private>true</Private>
                </Reference>"""
        ).rstrip()
        for name, path in spec.references
    )

    payload = textwrap.dedent(
        f"""\
        <Project Sdk="Microsoft.NET.Sdk">
          <PropertyGroup>
            <TargetFramework>{xml_utils.escape(spec.target_framework)}</TargetFramework>
            <AssemblyName>{xml_utils.escape(spec.assembly_name)}</AssemblyName>
            <RootNamespace>{xml_utils.escape(spec.assembly_name)}</RootNamespace>
            <OutputType>{xml_utils.escape(spec.output_type)}</OutputType>
            <Nullable>disable</Nullable>
            <ImplicitUsings>disable</ImplicitUsings>
            <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
            <AppendTargetFrameworkToOutputPath>false</AppendTargetFrameworkToOutputPath>
            <AppendRuntimeIdentifierToOutputPath>false</AppendRuntimeIdentifierToOutputPath>
            <UseAppHost>false</UseAppHost>
            <OutputPath>{xml_utils.escape(spec.output_dir)}</OutputPath>
          </PropertyGroup>
          <ItemGroup>
        {compile_items}
          </ItemGroup>"""
    )
    if reference_items:
        payload += "\n  <ItemGroup>\n"
        payload += textwrap.indent(reference_items, "    ")
        payload += "\n  </ItemGroup>"
    payload += "\n</Project>\n"

    with open(spec.project_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def _run_dotnet_build(dotnet: str, spec: _GeneratedProjectSpec) -> None:
    normalized_intermediate_dir = os.path.join(spec.intermediate_dir, "")
    subprocess.run(
        [
            dotnet,
            "build",
            spec.project_path,
            "-c",
            "Release",
            "--nologo",
            f"-p:BaseIntermediateOutputPath={normalized_intermediate_dir}",
            f"-p:MSBuildProjectExtensionsPath={normalized_intermediate_dir}",
            f"-p:IntermediateOutputPath={normalized_intermediate_dir}",
        ],
        check=True,
    )


def _build_generated_project(dotnet: str, spec: _GeneratedProjectSpec) -> None:
    _write_generated_project(spec)
    _run_dotnet_build(dotnet, spec)


def _write_dotnet_launcher(path: str, dll_path: str) -> None:
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    payload = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if ! command -v dotnet >/dev/null 2>&1; then\n"
        "  echo \"dotnet is required to run this build artifact.\" >&2\n"
        "  exit 1\n"
        "fi\n"
        f'exec dotnet "{dll_path}" "$@"\n'
    )
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    os.chmod(path, 0o755)


def _build_core_sdk(
    *,
    dotnet: str,
    repo_root: str,
    version: str,
    assembly_name: str,
    target_framework: str,
    source_roots: list[str],
    dependency_references: list[tuple[str, str]],
) -> str:
    source_files = _collect_csharp_files(repo_root, source_roots)
    build_dir = os.path.join(repo_root, "build", version)
    sdk_dir = os.path.join(build_dir, "sdk")
    output_dir = os.path.join(sdk_dir, "lib")
    intermediate_dir = os.path.join(build_dir, "obj", "sdk")
    _prepare_dir(output_dir)
    _prepare_dir(intermediate_dir)

    spec = _GeneratedProjectSpec(
        project_path=os.path.join(build_dir, "kbuild", "core", f"{assembly_name}.csproj"),
        assembly_name=assembly_name,
        target_framework=target_framework,
        output_type="Library",
        output_dir=output_dir,
        intermediate_dir=intermediate_dir,
        source_files=source_files,
        references=dependency_references,
    )
    _build_generated_project(dotnet, spec)
    return os.path.join(output_dir, f"{assembly_name}.dll")


def _build_tests(
    *,
    dotnet: str,
    repo_root: str,
    version: str,
    assembly_name: str,
    target_framework: str,
    test_roots: list[str],
    references: list[tuple[str, str]],
) -> None:
    if not test_roots:
        return

    source_files = _collect_csharp_files(repo_root, test_roots)
    tests_root = os.path.join(repo_root, "build", version, "tests")
    output_dir = os.path.join(tests_root, "bin")
    intermediate_dir = os.path.join(tests_root, "obj")
    _prepare_dir(output_dir)
    _prepare_dir(intermediate_dir)

    test_assembly_name = f"{assembly_name}.Tests"
    spec = _GeneratedProjectSpec(
        project_path=os.path.join(tests_root, "kbuild", f"{test_assembly_name}.csproj"),
        assembly_name=test_assembly_name,
        target_framework=target_framework,
        output_type="Exe",
        output_dir=output_dir,
        intermediate_dir=intermediate_dir,
        source_files=source_files,
        references=references,
    )
    _build_generated_project(dotnet, spec)
    _write_dotnet_launcher(
        os.path.join(tests_root, "run-tests"),
        os.path.join(output_dir, f"{test_assembly_name}.dll"),
    )


def _demo_shared_roots(demo_root: str, demo_name: str) -> list[str]:
    roots = [os.path.join(demo_root, "common", "src")]
    if demo_name.startswith("sdk/"):
        roots.append(os.path.join(demo_root, "sdk", "common", "src"))
    return roots


def _build_demo(
    *,
    dotnet: str,
    repo_root: str,
    demo_root: str,
    demo_name: str,
    version: str,
    target_framework: str,
    references: list[tuple[str, str]],
    built_demo_sdk_references: list[tuple[str, str]],
) -> tuple[str, str] | None:
    source_dir = os.path.join(repo_root, demo_root, demo_name, "src")
    if not os.path.isdir(source_dir):
        errors.die(f"csharp demo source directory does not exist: {source_dir}")

    roots = []
    for candidate in _demo_shared_roots(os.path.join(repo_root, demo_root), demo_name):
        if os.path.isdir(candidate):
            roots.append(candidate)
    roots.append(source_dir)
    source_files = _collect_csharp_files(repo_root, [os.path.relpath(root, repo_root) for root in roots])

    normalized_demo_name = demo_name.replace("/", ".").replace("\\", ".")
    demo_build_dir = os.path.join(repo_root, demo_root, demo_name, "build", version)

    if demo_name.startswith("sdk/"):
        demo_assembly_name = f"{normalized_demo_name}".replace(".", "_")
        demo_assembly_name = "".join(
            part[:1].upper() + part[1:] for part in demo_assembly_name.split("_") if part
        )
        output_dir = os.path.join(demo_build_dir, "sdk", "lib")
        intermediate_dir = os.path.join(demo_build_dir, "obj")
        _prepare_dir(output_dir)
        _prepare_dir(intermediate_dir)
        spec = _GeneratedProjectSpec(
            project_path=os.path.join(demo_build_dir, "kbuild", f"{demo_assembly_name}.csproj"),
            assembly_name=demo_assembly_name,
            target_framework=target_framework,
            output_type="Library",
            output_dir=output_dir,
            intermediate_dir=intermediate_dir,
            source_files=source_files,
            references=[*references, *built_demo_sdk_references],
        )
        _build_generated_project(dotnet, spec)
        dll_path = os.path.join(output_dir, f"{demo_assembly_name}.dll")
        print(f"Build complete -> dir={demo_build_dir} | sdk={os.path.join(demo_build_dir, 'sdk')}")
        return demo_assembly_name, dll_path

    demo_assembly_name = "".join(
        part[:1].upper() + part[1:]
        for part in normalized_demo_name.replace(".", "_").split("_")
        if part
    )
    output_dir = os.path.join(demo_build_dir, "bin")
    intermediate_dir = os.path.join(demo_build_dir, "obj")
    _prepare_dir(output_dir)
    _prepare_dir(intermediate_dir)
    spec = _GeneratedProjectSpec(
        project_path=os.path.join(demo_build_dir, "kbuild", f"{demo_assembly_name}.csproj"),
        assembly_name=demo_assembly_name,
        target_framework=target_framework,
        output_type="Exe",
        output_dir=output_dir,
        intermediate_dir=intermediate_dir,
        source_files=source_files,
        references=[*references, *built_demo_sdk_references],
    )
    _build_generated_project(dotnet, spec)
    launcher_name = "bootstrap" if demo_name == "bootstrap" else "test"
    _write_dotnet_launcher(
        os.path.join(demo_build_dir, launcher_name),
        os.path.join(output_dir, f"{demo_assembly_name}.dll"),
    )
    print(f"Build complete -> dir={demo_build_dir} | sdk=<none>")
    return None


def build_repo(
    *,
    repo_root: str,
    version: str,
    build_demos: bool,
    requested_demos: list[str],
    config_build_demos: list[str],
    config_default_build_demos: list[str],
) -> int:
    dotnet = _ensure_dotnet()
    (
        assembly_name,
        source_roots,
        test_roots,
        demo_root,
        target_framework,
        dependency_templates,
    ) = _load_csharp_config(repo_root)

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

    dependency_references = _resolve_dependency_references(
        repo_root=repo_root,
        version=version,
        dependency_templates=dependency_templates,
    )
    core_dll_path = _build_core_sdk(
        dotnet=dotnet,
        repo_root=repo_root,
        version=version,
        assembly_name=assembly_name,
        target_framework=target_framework,
        source_roots=source_roots,
        dependency_references=dependency_references,
    )

    sdk_dir = os.path.join(repo_root, "build", version, "sdk")
    print(f"Build complete -> dir=build/{version} | sdk={sdk_dir}")

    core_references = [(assembly_name, core_dll_path), *dependency_references]
    _build_tests(
        dotnet=dotnet,
        repo_root=repo_root,
        version=version,
        assembly_name=assembly_name,
        target_framework=target_framework,
        test_roots=test_roots,
        references=core_references,
    )

    if not demo_order:
        return 0

    built_demo_sdk_references: list[tuple[str, str]] = []
    for demo_name in demo_order:
        print(
            f"Demo build -> dir={os.path.join(demo_root, demo_name, 'build', version)} | demo={demo_name} | sdk={sdk_dir}",
            flush=True,
        )
        built_demo = _build_demo(
            dotnet=dotnet,
            repo_root=repo_root,
            demo_root=demo_root,
            demo_name=demo_name,
            version=version,
            target_framework=target_framework,
            references=core_references,
            built_demo_sdk_references=built_demo_sdk_references,
        )
        if built_demo is not None:
            built_demo_sdk_references.append(built_demo)

    return 0
