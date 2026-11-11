#!/bin/bash
# Builds the distributable plugin package: dist/chromadb-<version>.zip (+ .sha256)
# Usage: bash build.sh [output_dir]
set -euo pipefail
cd "$(dirname "$0")"
SRC="$(pwd)"
NAME=chromadb
OUT="${1:-$SRC/dist}"
PY=/www/server/panel/pyenv/bin/python
[ -x "$PY" ] || PY=python3

VERSION=$($PY -c "import json;print(json.load(open('info.json'))['versions'])")
CODE_VERSION=$(grep -oP '^PLUGIN_VERSION = "\K[^"]+' chromadb_main.py)
if [ "$VERSION" != "$CODE_VERSION" ]; then
  echo "Version mismatch: info.json=$VERSION chromadb_main.py=$CODE_VERSION"; exit 1
fi

echo "==> Checks"
for f in info.json install.sh chromadb_main.py index.html icon.png scripts/setup.sh scripts/remove.sh README.md LICENSE CHANGELOG.md; do
  [ -f "$f" ] || { echo "Missing $f"; exit 1; }
done
$PY -c "import json;json.load(open('info.json'))"
$PY -m py_compile chromadb_main.py
bash -n install.sh scripts/setup.sh scripts/remove.sh
rm -rf __pycache__

echo "==> Packaging $NAME $VERSION"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/$NAME/scripts"
cp info.json install.sh chromadb_main.py index.html icon.png README.md LICENSE CHANGELOG.md "$STAGE/$NAME/"
cp scripts/setup.sh scripts/remove.sh "$STAGE/$NAME/scripts/"
mkdir -p "$OUT"
ZIP="$OUT/$NAME-$VERSION.zip"
rm -f "$ZIP"
(cd "$STAGE" && zip -qrX "$ZIP" "$NAME")
(cd "$OUT" && sha256sum "$(basename "$ZIP")" > "$(basename "$ZIP").sha256")
unzip -l "$ZIP"
echo "==> $ZIP"
cat "$ZIP.sha256"
