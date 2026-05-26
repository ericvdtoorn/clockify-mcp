"""Build clockify.dxt — bundles manifest.json, server.py, and vendored deps.

Vendoring uses `uv pip install --target build/lib .`, which picks wheels for
the host platform. The resulting .dxt only works on platforms whose wheels were
fetched (linux/macos/windows differ for pydantic-core); rebuild per platform
or pass --python-platform to uv if you need cross-platform bundles.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
LIB = BUILD / "lib"
DXT = ROOT / "clockify.dxt"


def main() -> int:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    DXT.unlink(missing_ok=True)

    LIB.mkdir(parents=True)

    subprocess.run(
        ["uv", "pip", "install", "--target", str(LIB), str(ROOT)],
        check=True,
    )

    # Strip caches. Keep *.dist-info — mcp reads its own version via
    # importlib.metadata at import time and will fail without it.
    for path in LIB.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)
    for lock in LIB.glob(".lock"):
        lock.unlink()

    shutil.copy(ROOT / "manifest.json", BUILD / "manifest.json")
    shutil.copy(ROOT / "server.py", BUILD / "server.py")

    with zipfile.ZipFile(DXT, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(BUILD.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(BUILD))

    size_mb = DXT.stat().st_size / (1024 * 1024)
    print(f"built {DXT.name} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
