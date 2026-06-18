#!/usr/bin/env bash
# Build the integrated WebUI and copy the output into the plugin's webui/ directory.
#
# Usage:
#   bash build_webui.sh              # full build
#   bash build_webui.sh --skip-install  # skip npm install

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_SRC_DIR="${PLUGIN_DIR}/web"
WEBUI_OUT_DIR="${PLUGIN_DIR}/webui"
WEB_BUILD_DIR="${WEB_SRC_DIR}/dist/web"

SKIP_INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --skip-install) SKIP_INSTALL=1 ;;
  esac
done

if [ ! -d "${WEB_SRC_DIR}" ]; then
  echo "ERROR: web source directory not found at ${WEB_SRC_DIR}" >&2
  echo "The web/ directory should contain the web frontend source code." >&2
  exit 1
fi

if [ "${SKIP_INSTALL}" -eq 0 ]; then
  echo "=== Installing npm dependencies ==="
  (cd "${WEB_SRC_DIR}" && npm install)
fi

echo "=== Building WebUI (web target) ==="
(cd "${WEB_SRC_DIR}" && npm run build:web)

if [ ! -d "${WEB_BUILD_DIR}" ]; then
  echo "ERROR: build output not found at ${WEB_BUILD_DIR}" >&2
  exit 1
fi

echo "=== Copying build output to ${WEBUI_OUT_DIR} ==="
rm -rf "${WEBUI_OUT_DIR}"
cp -r "${WEB_BUILD_DIR}" "${WEBUI_OUT_DIR}"

echo ""
echo "WebUI built successfully and copied to ${WEBUI_OUT_DIR}"
echo "Start AstrBot and visit http://127.0.0.1:12397/ to access the WebUI."
