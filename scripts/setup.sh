#!/bin/bash
# ChromaDB runtime installer/upgrader for the aaPanel plugin.
# Usage: setup.sh <version>     (idempotent: also used for upgrades)
set -euo pipefail
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

VERSION="${1:-1.5.9}"
ROOT=/www/server/chromadb
PLUGIN=/www/server/panel/plugin/chromadb
PYVER=3.12
SVC_USER=chroma
export UV_PYTHON_INSTALL_DIR="$ROOT/python"
export UV_CACHE_DIR="$ROOT/.uv-cache"
export UV_NO_PROGRESS=1

trap 'rc=$?; rm -f "$ROOT/install.lock"; rm -rf "$UV_CACHE_DIR"; if [ $rc -ne 0 ]; then echo; echo "==> FAILED (exit code $rc)"; fi' EXIT

echo "==> Installing ChromaDB $VERSION ($(date '+%F %T'))"

# --- Pre-flight checks ---
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid version: $VERSION"; exit 1
fi
if ! pidof systemd >/dev/null 2>&1 && [ ! -d /run/systemd/system ]; then
  echo "systemd is required"; exit 1
fi
case "$(uname -m)" in
  x86_64|aarch64) ;;
  *) echo "Unsupported architecture: $(uname -m) (x86_64 or aarch64 required)"; exit 1 ;;
esac
echo "    OS: $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-unknown}") | arch: $(uname -m) | systemd: $(systemctl --version | head -1 | awk '{print $2}')"

if ! command -v uv >/dev/null 2>&1; then
  echo "==> uv not found; installing it with the panel's pip"
  /www/server/panel/pyenv/bin/pip install -q uv
  ln -sf /www/server/panel/pyenv/bin/uv /usr/local/bin/uv
fi
echo "    uv: $(uv --version)"

echo "==> Service user '$SVC_USER'"
if ! id "$SVC_USER" >/dev/null 2>&1; then
  NOLOGIN=$(command -v nologin || echo /sbin/nologin)
  useradd --system --no-create-home --home-dir "$ROOT" --shell "$NOLOGIN" "$SVC_USER"
fi

echo "==> Directories"
mkdir -p "$ROOT/data"
chmod 755 "$ROOT"
chown -R "$SVC_USER:$SVC_USER" "$ROOT/data"
chmod 700 "$ROOT/data"

echo "==> Isolated Python $PYVER in $UV_PYTHON_INSTALL_DIR"
uv python install "$PYVER"

if [ ! -x "$ROOT/venv/bin/python" ]; then
  echo "==> Creating virtualenv"
  uv venv -q -p "$PYVER" "$ROOT/venv"
fi

echo "==> Installing chromadb==$VERSION (this can take a few minutes)"
uv pip install -p "$ROOT/venv/bin/python" "chromadb==$VERSION"

# Only root can write the code; the service can only read it
chown -R root:root "$ROOT/venv" "$ROOT/python"
chmod -R go-w "$ROOT/venv" "$ROOT/python"

echo "==> Applying configuration and systemd service"
/www/server/panel/pyenv/bin/python "$PLUGIN/chromadb_main.py" apply

echo
echo "==> DONE: ChromaDB $VERSION installed and running on 127.0.0.1"
