#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip

if compgen -G "${ROOT_DIR}/wheels/*.whl" > /dev/null; then
  python -m pip install "${ROOT_DIR}"/wheels/*.whl
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
