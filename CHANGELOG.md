# Changelog

## 1.1.1 — 2026-11-10
- Fix: creating databases/collections, deleting collections and restoring/deleting backups did nothing from the UI.
  The form field `name` overrode the `name=chromadb` routing key of aaPanel's `/plugin` endpoint, so the request
  was sent to a non-existent plugin. Parameters renamed to `db_name`, `collection` and `file`.

## 1.1.0 — 2026-11-10
- English / Spanish interface (follows the panel language; switchable in the plugin).
- Version picker fed from PyPI (stable releases ≥ 1.0.0, with dates; cached 6 h; offline fallback).
- Install refuses versions that do not exist on PyPI or are older than 1.0.0.
- Remote access opens/closes the port in the aaPanel firewall automatically, only for the allow-listed IPs.
- SSL option is disabled (with an explanation) when nginx is older than 1.25.1.
- Pre-flight checks in the installer (systemd, architecture) and a language-independent success marker.
- `chromadb_main.py backup` CLI command for scheduled backups via panel Cron.
- README, LICENSE (MIT) and `build.sh` packaging script.

## 1.0.0 — 2026-11-10
- First version: install/upgrade/uninstall, hardened systemd service bound to 127.0.0.1,
  nginx token proxy with IP allow-list, rate limit and optional SSL, collections, backups, logs.
