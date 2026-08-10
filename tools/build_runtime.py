"""Build and diff planning helpers for the compiled MicroPython runtime."""

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


VERSION_FILE = "uhs-version.txt"
COMPILE_EXCEPTIONS = {"main.py", "config.py.example"}
PROTECTED_CONFIG = {"config.py", "config.py.example"}
EXCLUDED_PREFIXES = ("docs/", "firmware/", ".github/", "tools/")


@dataclass(frozen=True)
class BuildReport:
    files: tuple
    compiled: tuple
    direct: tuple


@dataclass(frozen=True)
class DiffPlan:
    archive_paths: tuple
    delete_paths: tuple
    first_mpy_migration: bool


def _normalize(path):
    return str(path or "").replace("\\", "/").strip("/")


def include_runtime_path(path):
    text = _normalize(path)
    lower = text.lower()
    if not text or text in (".", ".."):
        return False
    if text == "config.py":
        return False
    if lower == "license" or lower == ".gitignore":
        return False
    if lower.endswith(".md"):
        return False
    if lower.startswith(EXCLUDED_PREFIXES):
        return False
    if "/examples/" in lower or lower.startswith("examples/") or lower.endswith("/examples"):
        return False
    name = lower.rsplit("/", 1)[-1]
    if name.endswith(".example") and lower != "config.py.example":
        return False
    if "example" in name and lower != "config.py.example":
        return False
    if lower.startswith("assets/icons/origin/") or "/icons/origin/" in lower:
        return False
    return True


def should_compile(path):
    text = _normalize(path)
    return (
        include_runtime_path(text)
        and text.lower().endswith(".py")
        and text not in COMPILE_EXCEPTIONS
    )


def artifact_path(path):
    text = _normalize(path)
    if should_compile(text):
        return text[:-3] + ".mpy"
    return text


def _tracked_paths(source_root):
    result = subprocess.run(
        ["git", "-C", str(source_root), "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def _compile_with_mpy_cross(mpy_cross, source_path, output_path, source_root):
    subprocess.run(
        [str(mpy_cross), str(source_path), "-o", str(output_path)],
        check=True,
        cwd=str(source_root),
    )


def build_staging(
    source_root,
    staging_root,
    version,
    mpy_cross=None,
    compile_file=None,
    tracked_paths=None,
):
    source_root = Path(source_root)
    staging_root = Path(staging_root)
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)

    if tracked_paths is None:
        tracked_paths = _tracked_paths(source_root)

    compiled = []
    direct = []
    for raw_path in sorted(tracked_paths):
        relative = _normalize(raw_path)
        if not include_runtime_path(relative):
            continue
        source_path = source_root / Path(*relative.split("/"))
        if not source_path.is_file():
            raise RuntimeError("Tracked runtime file is missing: {}".format(relative))

        output_relative = artifact_path(relative)
        output_path = staging_root / Path(*output_relative.split("/"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if should_compile(relative):
            if compile_file is not None:
                compile_file(source_path, output_path)
            elif mpy_cross is not None:
                _compile_with_mpy_cross(mpy_cross, source_path, output_path, source_root)
            else:
                raise RuntimeError("Missing mpy-cross compiler")
            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise RuntimeError("mpy-cross produced no output for {}".format(relative))
            compiled.append(output_relative)
        else:
            shutil.copyfile(source_path, output_path)
            direct.append(output_relative)

    version_path = staging_root / VERSION_FILE
    version_path.write_text(str(version or "") + "\n", encoding="utf-8")
    direct.append(VERSION_FILE)

    required = ("main.py", "config.py.example")
    for required_path in required:
        if not (staging_root / required_path).is_file():
            raise RuntimeError("Required runtime file is missing: {}".format(required_path))
    unexpected_sources = []
    for path in staging_root.rglob("*.py"):
        relative = path.relative_to(staging_root).as_posix()
        if relative not in COMPILE_EXCEPTIONS:
            unexpected_sources.append(relative)
    if unexpected_sources:
        raise RuntimeError(
            "Unexpected Python sources in staging: {}".format(", ".join(sorted(unexpected_sources)))
        )

    files = sorted(
        path.relative_to(staging_root).as_posix()
        for path in staging_root.rglob("*")
        if path.is_file()
    )
    return BuildReport(tuple(files), tuple(sorted(compiled)), tuple(sorted(direct)))


def _entry(status, paths):
    if isinstance(paths, str):
        paths = (paths,)
    return str(status or ""), tuple(_normalize(path) for path in paths)


def _delete_variants(path, deletes):
    relative = _normalize(path)
    if not relative or relative in PROTECTED_CONFIG:
        return
    if should_compile(relative):
        deletes.add(relative)
        deletes.add(artifact_path(relative))
    else:
        deletes.add(relative)


def _add_archive(path, staging_root, archives):
    relative = _normalize(path)
    if not relative:
        return
    if not include_runtime_path(relative):
        return
    mapped = artifact_path(relative)
    if (Path(staging_root) / Path(*mapped.split("/"))).is_file():
        archives.add(mapped)


def plan_diff(changed_paths, base_paths, staging_root):
    normalized_base = {_normalize(path) for path in base_paths}
    first_mpy_migration = "tools/build_runtime.py" not in normalized_base
    archives = set()
    deletes = set()

    parsed = []
    for item in changed_paths:
        if isinstance(item, dict):
            status = item.get("status", "")
            paths = item.get("paths", ())
        else:
            status = item[0]
            paths = item[1:]
        parsed.append(_entry(status, paths))

    if first_mpy_migration:
        staging_root = Path(staging_root)
        for path in staging_root.rglob("*.mpy"):
            archives.add(path.relative_to(staging_root).as_posix())
        for path in normalized_base:
            if should_compile(path):
                deletes.add(path)

    for status, paths in parsed:
        normalized_status = status.upper()
        if normalized_status.startswith("R") and len(paths) >= 2:
            _delete_variants(paths[0], deletes)
            _add_archive(paths[-1], staging_root, archives)
            continue
        if normalized_status.startswith("D"):
            _delete_variants(paths[-1], deletes)
            continue
        if normalized_status.startswith(("A", "M", "T", "C")):
            _add_archive(paths[-1], staging_root, archives)

    _add_archive(VERSION_FILE, staging_root, archives)
    deletes.difference_update(PROTECTED_CONFIG)
    return DiffPlan(
        tuple(sorted(archives)),
        tuple(sorted(deletes)),
        first_mpy_migration,
    )


def _git_diff_paths(source_root, base_ref, head_ref):
    result = subprocess.run(
        [
            "git",
            "-C",
            str(source_root),
            "diff",
            "--name-status",
            "-z",
            str(base_ref),
            str(head_ref),
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    fields = [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    entries = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if status.startswith(("R", "C")):
            entries.append((status, fields[index], fields[index + 1]))
            index += 2
        else:
            entries.append((status, fields[index]))
            index += 1
    return entries


def _git_tree_paths(source_root, ref):
    result = subprocess.run(
        ["git", "-C", str(source_root), "ls-tree", "-r", "--name-only", str(ref)],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def plan_git_diff(source_root, base_ref, head_ref, staging_root):
    return plan_diff(
        _git_diff_paths(source_root, base_ref, head_ref),
        _git_tree_paths(source_root, base_ref),
        staging_root,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--staging-root", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--mpy-cross", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.mpy_cross.is_file():
        raise SystemExit("mpy-cross executable not found: {}".format(args.mpy_cross))
    build_staging(
        args.source_root,
        args.staging_root,
        args.version,
        mpy_cross=args.mpy_cross,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
