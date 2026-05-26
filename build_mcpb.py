"""Build clockify.mcpb — zips manifest.json, pyproject.toml, src/, and license.

With `server.type: "uv"` the host runs `uv run --directory <bundle> clockify-mcp`,
so the bundle ships source only — no vendored dependencies or platform-specific
binaries. uv resolves and installs everything (including Python itself, via
python-build-standalone) at first launch.
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INCLUDE = [
    "manifest.json",
    "pyproject.toml",
    "README.md",
    "LICENSE",
]
INCLUDE_TREES = ["src"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="clockify.mcpb", help="Output filename.")
    args = parser.parse_args()

    out = ROOT / args.output
    out.unlink(missing_ok=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in INCLUDE:
            z.write(ROOT / name, name)
        for tree in INCLUDE_TREES:
            for path in sorted((ROOT / tree).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    z.write(path, path.relative_to(ROOT))

    size_kb = out.stat().st_size / 1024
    print(f"built {out.name} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
