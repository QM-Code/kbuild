from . import cargo_backend
from . import cmake_backend
from . import csharp_backend
from . import errors
from . import javascript_backend
from . import java_backend
from . import kotlin_backend
from . import python_backend
from . import swift_backend
from .config_ops import KbuildConfig


def _require_non_cmake_backend_safe(
    *,
    backend_name: str,
    configure_flag_seen: bool,
    cmake_jobs_override: int | None,
    cmake_linkage_override: str | None,
    install_vcpkg: bool,
    has_vcpkg: bool,
) -> None:
    if configure_flag_seen:
        errors.die(f"cmake configure options are not supported for {backend_name} repos")
    if cmake_jobs_override is not None:
        errors.die(f"--cmake-jobs is not supported for {backend_name} repos")
    if cmake_linkage_override is not None:
        errors.die(f"--cmake-linkage is not supported for {backend_name} repos")
    if install_vcpkg or has_vcpkg:
        errors.die(f"vcpkg is not supported for {backend_name} repos")


def run_backend(
    *,
    repo_root: str,
    config: KbuildConfig,
    version: str,
    build_demos: bool,
    requested_demos: list[str],
    configure_override: bool | None,
    configure_flag_seen: bool,
    cmake_jobs_override: int | None,
    cmake_linkage_override: str | None,
    install_vcpkg: bool,
) -> int | None:
    backend_name = config.backend_name
    if backend_name is None:
        return None

    if backend_name == "cmake":
        return cmake_backend.build_repo(
            repo_root=repo_root,
            config=config,
            version=version,
            build_demos=build_demos,
            requested_demos=requested_demos,
            configure_override=configure_override,
            cmake_jobs_override=cmake_jobs_override,
            cmake_linkage_override=cmake_linkage_override,
        )

    _require_non_cmake_backend_safe(
        backend_name=backend_name,
        configure_flag_seen=configure_flag_seen,
        cmake_jobs_override=cmake_jobs_override,
        cmake_linkage_override=cmake_linkage_override,
        install_vcpkg=install_vcpkg,
        has_vcpkg=config.has_vcpkg,
    )

    if backend_name == "cargo":
        return cargo_backend.build_repo(
            repo_root=repo_root,
            config=config,
            version=version,
            build_demos=build_demos,
            requested_demos=requested_demos,
        )
    if backend_name == "java":
        return java_backend.build_repo(
            repo_root=repo_root,
            version=version,
            build_demos=build_demos,
            requested_demos=requested_demos,
            config_build_demos=config.build_demos,
            config_default_build_demos=config.default_build_demos,
        )
    if backend_name == "swift":
        return swift_backend.build_repo(
            repo_root=repo_root,
            version=version,
            build_demos=build_demos,
            requested_demos=requested_demos,
            config_build_demos=config.build_demos,
            config_default_build_demos=config.default_build_demos,
        )
    if backend_name == "kotlin":
        return kotlin_backend.build_repo(
            repo_root=repo_root,
            version=version,
            build_demos=build_demos,
            requested_demos=requested_demos,
            config_build_demos=config.build_demos,
            config_default_build_demos=config.default_build_demos,
        )
    if backend_name == "csharp":
        return csharp_backend.build_repo(
            repo_root=repo_root,
            version=version,
            build_demos=build_demos,
            requested_demos=requested_demos,
            config_build_demos=config.build_demos,
            config_default_build_demos=config.default_build_demos,
        )
    if backend_name == "javascript":
        return javascript_backend.build_repo(
            repo_root=repo_root,
            version=version,
            build_demos=build_demos,
            requested_demos=requested_demos,
            config_build_demos=config.build_demos,
            config_default_build_demos=config.default_build_demos,
        )

    errors.die(f"unknown internal backend '{backend_name}'")


def find_unexpected_residuals(
    *,
    repo_root: str,
    config: KbuildConfig,
) -> tuple[str, list[str]] | None:
    backend_name = config.backend_name
    if backend_name is None:
        return None

    if backend_name == "cargo":
        finding = cargo_backend.find_unexpected_residuals(repo_root)
    elif backend_name == "java":
        finding = java_backend.find_unexpected_residuals(repo_root)
    elif backend_name == "swift":
        finding = swift_backend.find_unexpected_residuals(repo_root)
    elif backend_name == "kotlin":
        finding = kotlin_backend.find_unexpected_residuals(repo_root)
    elif backend_name == "csharp":
        finding = csharp_backend.find_unexpected_residuals(repo_root)
    elif backend_name == "javascript":
        finding = javascript_backend.find_unexpected_residuals(repo_root)
    else:
        finding = None

    if finding is not None:
        return finding

    if python_backend.is_enabled(repo_root):
        return python_backend.find_unexpected_residuals(repo_root)

    return None
