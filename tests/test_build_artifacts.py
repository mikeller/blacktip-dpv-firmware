# Test suite for build artifacts module.
# Detected testing framework: pytest (preferred if available); falls back to unittest-style asserts if pytest not installed.
import os
import json
import pathlib
from typing import Any, Dict

try:
    import pytest  # type: ignore
except ImportError:  # pragma: no cover
    pytest = None  # minimal fallback

# Lazy imports of the source-under-test to avoid hard-coding paths.
# We try common module names; if they don't exist, tests using them will be skipped.
MODULE_CANDIDATES = [
    "build_artifacts",
    "src.build_artifacts",
    "app.build_artifacts",
    "tools.build_artifacts",
    "ci.build_artifacts",
]

def _import_first_available(mod_names):
    import importlib
    for name in mod_names:
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    return None

BA = _import_first_available(MODULE_CANDIDATES)

collect_fn = getattr(BA, "collect_build_artifacts", None) if BA else None
package_fn = getattr(BA, "package_build_artifacts", None) if BA else None
validate_fn = getattr(BA, "validate_artifact_manifest", None) if BA else None

pytestmark = []
if pytest is not None:
    if collect_fn is None:
        pytestmark.append(pytest.mark.skip(reason="collect_build_artifacts not found"))
    if package_fn is None:
        pytestmark.append(pytest.mark.skip(reason="package_build_artifacts not found"))
    if validate_fn is None:
        # Not fatal; only tests that need it will be skipped.
        pass

def _write_file(path: pathlib.Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def _touch(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()

def _manifest(items: Dict[str, Any]) -> Dict[str, Any]:
    return items

def test_collect_build_artifacts_happy_path(tmp_path: pathlib.Path):
    if collect_fn is None:
        return
    # Arrange: create a fake build directory with files to collect
    build_dir = tmp_path / "build"
    _write_file(build_dir / "app.whl", "wheel-bytes")
    _write_file(build_dir / "app.tar.gz", "tgz-bytes")
    _write_file(build_dir / "README.md", "docs")  # should be includable or excludable based on implementation

    # Some implementations need patterns; default to collect common artifact extensions
    include = ["*.whl", "*.tar.gz", "*.zip"]
    exclude = ["**/*.md"]  # common exclusion

    # Act
    artifacts = collect_fn(str(build_dir), include=include, exclude=exclude)

    # Assert
    assert isinstance(artifacts, list), "collect_build_artifacts should return a list of paths or dicts"  # noqa: B101
    flat = [str(a) for a in artifacts]
    assert any(p.endswith("app.whl") for p in flat)  # noqa: B101
    assert any(p.endswith("app.tar.gz") for p in flat)  # noqa: B101
    assert not any(p.endswith("README.md") for p in flat)  # noqa: B101

def test_collect_build_artifacts_empty_dir(tmp_path: pathlib.Path):
    if collect_fn is None:
        return
    build_dir = tmp_path / "empty"
    build_dir.mkdir(parents=True, exist_ok=True)

    artifacts = collect_fn(str(build_dir), include=["*"], exclude=[])
    assert isinstance(artifacts, list)  # noqa: B101
    assert artifacts == [] or len(artifacts) == 0  # noqa: B101

def test_collect_build_artifacts_invalid_path(tmp_path: pathlib.Path):
    if collect_fn is None:
        return
    missing = tmp_path / "nope"
    try:
        res = collect_fn(str(missing), include=["*"], exclude=[])
    except (FileNotFoundError, ValueError):
        # Expected: raise a FileNotFoundError or ValueError
        pass
    else:
        assert res == []  # noqa: B101

def test_validate_artifact_manifest_success():
    if validate_fn is None:
        return
    manifest = _manifest({
        "name": "app",
        "version": "1.2.3",
        "artifacts": [
            {"path": "dist/app-1.2.3.whl", "sha256": "deadbeef"*8},
            {"path": "dist/app-1.2.3.tar.gz", "sha256": "feedface"*8},
        ],
    })
    # Should not raise
    validate_fn(manifest)

def test_validate_artifact_manifest_missing_keys():
    if validate_fn is None:
        return
    bad = _manifest({"name": "app", "artifacts": []})  # missing version
    try:
        validate_fn(bad)
    except (KeyError, ValueError, AssertionError):
        pass
    else:
        raise AssertionError("validate_artifact_manifest should fail when required keys are missing")  # noqa: TRY003

def test_package_build_artifacts_creates_archive(tmp_path: pathlib.Path):
    if package_fn is None:
        return
    # Arrange inputs: fake collected artifacts
    artifacts_dir = tmp_path / "build"
    _write_file(artifacts_dir / "pkg.whl", "abc")
    _write_file(artifacts_dir / "pkg.tar.gz", "xyz")

    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Some implementations accept (artifacts, output_path, manifest)
    # We'll try both common call signatures and skip if unsupported.
    archive = None
    try:
        archive = package_fn([str(artifacts_dir / "pkg.whl"), str(artifacts_dir / "pkg.tar.gz")], str(output_dir))
    except TypeError:
        # Alternate signature using kwargs
        archive = package_fn(artifacts=[str(artifacts_dir / "pkg.whl"), str(artifacts_dir / "pkg.tar.gz")], output_dir=str(output_dir))

    # Assert archive produced
    assert archive is not None  # noqa: B101
    arch_path = pathlib.Path(archive)
    assert arch_path.exists(), "Expected package_build_artifacts to create an archive"  # noqa: B101
    assert arch_path.stat().st_size > 0  # noqa: B101

def test_package_build_artifacts_overwrite_policy(tmp_path: pathlib.Path):
    if package_fn is None:
        return
    artifacts_dir = tmp_path / "build"
    _write_file(artifacts_dir / "a.whl", "1")
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    archive = None
    try:
        archive = package_fn([str(artifacts_dir / "a.whl")], str(out))
    except TypeError:
        archive = package_fn(artifacts=[str(artifacts_dir / "a.whl")], output_dir=str(out))
    assert archive  # noqa: B101
    arch = pathlib.Path(archive)
    # Try packaging again to check overwrite/unique naming behavior
    try:
        _ = package_fn([str(artifacts_dir / "a.whl")], str(out))
    except (FileExistsError, ValueError, RuntimeError):
        # If overwrite forbidden, an exception is acceptable
        pass
    else:
        # Otherwise, ensure the archive path still exists and is a file
        assert arch.exists()  # noqa: B101

def test_collect_build_artifacts_custom_patterns(tmp_path: pathlib.Path):
    if collect_fn is None:
        return
    root = tmp_path / "b"
    _write_file(root / "nested" / "bin.exe", "exe")
    _write_file(root / "nested" / "lib.dll", "dll")
    _write_file(root / "nested" / "notes.txt", "text")

    arts = collect_fn(str(root), include=["**/*.dll", "**/*.exe"], exclude=["**/*.txt"])
    s = set(map(lambda p: pathlib.Path(p).suffix, arts))
    assert ".dll" in s and ".exe" in s  # noqa: B101
    assert all(not str(p).endswith(".txt") for p in arts)  # noqa: B101