#!/bin/bash
# Uninstall the ChromaDB runtime. With --purge the data is deleted too.
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
ROOT=/www/server/chromadb

systemctl stop chromadb 2>/dev/null
systemctl disable chromadb 2>/dev/null
rm -f /etc/systemd/system/chromadb.service
systemctl daemon-reload

rm -rf "$ROOT/venv" "$ROOT/python" "$ROOT/.uv-cache" "$ROOT/config.yaml" "$ROOT/install.log" "$ROOT/install.lock" "$ROOT/versions_cache.json"

if [ "${1:-}" == "--purge" ]; then
  rm -rf "$ROOT"
  userdel chroma 2>/dev/null
  echo "Data deleted"
else
  echo "Data kept in $ROOT/data"
fi
exit 0
