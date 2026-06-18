#!/usr/bin/env python3
"""Build the integrated WebUI and copy the output into the plugin's ``webui/`` directory.

Usage::

    python build_webui.py          # full build (npm install + npm run build:web)
    python build_webui.py --skip-install  # skip npm install (reuse node_modules)

The script expects Node.js (>= 18) and npm to be available on PATH.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
WEB_SRC_DIR = PLUGIN_DIR / "web"
WEBUI_OUT_DIR = PLUGIN_DIR / "webui"
WEB_BUILD_DIR = WEB_SRC_DIR / "dist" / "web"


def _cmd(name: str) -> str:
    if os.name == "nt":
        resolved = shutil.which(f"{name}.cmd") or shutil.which(name)
        if resolved:
            return resolved
    return name


def _run(cmd: list[str], cwd: Path) -> None:
    print(f">>> {' '.join(cmd)}  (cwd={cwd})")
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(f"Command failed with exit code {result.returncode}: {' '.join(cmd)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the integrated WebUI.")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip `npm install` (reuse existing node_modules).",
    )
    args = parser.parse_args()

    if not WEB_SRC_DIR.exists():
        print(f"ERROR: web source directory not found at {WEB_SRC_DIR}", file=sys.stderr)
        print("The `web/` directory should contain the web frontend source code.", file=sys.stderr)
        raise SystemExit(1)

    # Step 1: Install dependencies
    if not args.skip_install:
        print("\n=== Installing npm dependencies ===")
        _run([_cmd("npm"), "install"], cwd=WEB_SRC_DIR)

    # Step 2: Build the web target
    print("\n=== Building WebUI (web target) ===")
    _run([_cmd("npm"), "run", "build:web"], cwd=WEB_SRC_DIR)

    if not WEB_BUILD_DIR.exists():
        print(f"ERROR: build output not found at {WEB_BUILD_DIR}", file=sys.stderr)
        raise SystemExit(1)

    # Step 3: Copy build output to webui/
    print(f"\n=== Copying build output to {WEBUI_OUT_DIR} ===")
    if WEBUI_OUT_DIR.exists():
        shutil.rmtree(WEBUI_OUT_DIR)
    shutil.copytree(WEB_BUILD_DIR, WEBUI_OUT_DIR)

    print(f"\nWebUI built successfully and copied to {WEBUI_OUT_DIR}")
    print("Start AstrBot and visit http://127.0.0.1:12397/ to access the WebUI.")


if __name__ == "__main__":
    main()
