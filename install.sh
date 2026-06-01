#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
python -m pip install --force-reinstall --no-cache-dir "Pillow>=10,<12.2"

if compgen -G "${ROOT_DIR}/wheels/*.whl" > /dev/null; then
  python -m pip install "${ROOT_DIR}"/wheels/*.whl
fi

PY_TAG="$(python -c 'import sys; print(f"cp{sys.version_info.major}{sys.version_info.minor}")')"
PLATFORM_KEY=""
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) PLATFORM_KEY="darwin-arm64" ;;
  Linux-x86_64|Linux-amd64) PLATFORM_KEY="linux-amd64" ;;
esac
if [[ -n "${PLATFORM_KEY}" ]]; then
  NATIVE_WHEEL_DIR="${ROOT_DIR}/wheels/${PLATFORM_KEY}"
  if compgen -G "${NATIVE_WHEEL_DIR}/cadis_native_cgd-*-${PY_TAG}-*.whl" > /dev/null; then
    python -m pip install "${NATIVE_WHEEL_DIR}"/cadis_native_cgd-*-${PY_TAG}-*.whl
  else
    echo "No compatible cadis_native_cgd wheel for ${PLATFORM_KEY}/${PY_TAG}; CADIS will use its Python CGD fallback."
  fi
else
  echo "No vendored cadis_native_cgd wheel for $(uname -s)-$(uname -m); CADIS will use its Python CGD fallback."
fi

if ! compgen -G "${ROOT_DIR}/wheels/cadis_travel_spark-*.whl" > /dev/null; then
  python -m pip install "${ROOT_DIR}"
fi

echo "TravelSpark installed. Activate with:"
echo "  source .venv/bin/activate"
echo "Then run:"
echo "  travelspark /path/to/photos --scene-id world_8192 --output travel.jpg"
echo "Or run without activating:"
echo "  .venv/bin/travelspark /path/to/photos --scene-id world_8192 --output travel.jpg"
