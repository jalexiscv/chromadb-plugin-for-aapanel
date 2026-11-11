#!/usr/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | ChromaDB Manager - third-party plugin for aaPanel
# +-------------------------------------------------------------------
# | Installs and manages a ChromaDB (vector database) server as a
# | hardened systemd service bound to 127.0.0.1 only. Optional remote
# | access goes through an nginx proxy with token auth, IP allow-list,
# | rate limiting and optional SSL.
# | License: MIT
# +-------------------------------------------------------------------
import ipaddress
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request

BASE_PATH = "/www/server/panel"
os.chdir(BASE_PATH)
sys.path.insert(0, "class/")
import public  # noqa: E402

PLUGIN_VERSION = "1.1.1"
PLUGIN_PATH = BASE_PATH + "/plugin/chromadb"
ROOT = "/www/server/chromadb"
VENV = ROOT + "/venv"
DATA = ROOT + "/data"
CONFIG_YAML = ROOT + "/config.yaml"
SETTINGS = ROOT + "/settings.json"
INSTALL_LOG = ROOT + "/install.log"
INSTALL_LOCK = ROOT + "/install.lock"
VERSIONS_CACHE = ROOT + "/versions_cache.json"
BACKUP_DIR = "/www/backup/chromadb"
UNIT_NAME = "chromadb"
UNIT_FILE = "/etc/systemd/system/chromadb.service"
SERVICE_USER = "chroma"
NGINX_CONF = BASE_PATH + "/vhost/nginx/chromadb_remote.conf"
NGINX_BIN = "/www/server/nginx/sbin/nginx"
CERT_ROOT = BASE_PATH + "/vhost/cert"
DEFAULT_VERSION = "1.5.9"
MIN_VERSION = (1, 0, 0)   # The plugin targets the Rust server (chroma run <config.yaml>)
TENANT = "default_tenant"
FW_BRIEF = "ChromaDB remote (plugin)"

DEFAULTS = {
    "version": DEFAULT_VERSION,
    "port": 8000,
    "memory_max": "2G",
    "lang": "",
    "remote": {
        "enabled": False,
        "port": 8800,
        "token": "",
        "whitelist": [],
        "ssl_site": "",
        "rate": 20,
        "fw_rules": [],
    },
}

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,510}[A-Za-z0-9]$")
BACKUP_RE = re.compile(r"^chromadb_\d{8}_\d{6}\.tar\.gz$")
MEM_RE = re.compile(r"^\d{1,6}[MG]$")
VER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# ----------------------------------------------------------------------
# i18n: English is the source language; Spanish translations below.
# ----------------------------------------------------------------------
ES = {
    "ChromaDB is not installed": "ChromaDB no está instalado",
    "Configuration applied": "Configuración aplicada",
    "The service did not respond after restarting. Check the logs.": "El servicio no respondió tras reiniciar. Revisa los logs.",
    "An installation is already in progress": "Ya hay una instalación en curso",
    "Invalid version": "Versión inválida",
    "Version {0} is not available on PyPI": "La versión {0} no está disponible en PyPI",
    "This plugin requires ChromaDB 1.0.0 or later": "Este plugin requiere ChromaDB 1.0.0 o superior",
    "Installation started": "Instalación iniciada",
    "An installation is in progress": "Hay una instalación en curso",
    "Uninstall error: ": "Error al desinstalar: ",
    "ChromaDB uninstalled": "ChromaDB desinstalado",
    ". Data kept in ": ". Los datos se conservaron en ",
    "Invalid action": "Acción inválida",
    "The service started but does not respond. Check the logs.": "El servicio arrancó pero no responde. Revisa los logs.",
    "Service started": "Servicio iniciado",
    "Service stopped": "Servicio detenido",
    "Service restarted": "Servicio reiniciado",
    "Invalid port": "Puerto inválido",
    "Port must be between 1024 and 65535": "El puerto debe estar entre 1024 y 65535",
    "Invalid memory limit (e.g. 512M, 2G)": "Límite de memoria inválido (ej.: 512M, 2G)",
    "Port {0} is already in use": "El puerto {0} ya está en uso",
    "Port matches the remote access port": "El puerto coincide con el del acceso remoto",
    "Saved": "Guardado",
    "Remote access disabled": "Acceso remoto desactivado",
    "Install ChromaDB first": "Instala ChromaDB primero",
    "Invalid numeric values": "Valores numéricos inválidos",
    "Invalid remote port (1024-65535 and different from the internal port)": "Puerto remoto inválido (1024-65535 y distinto del puerto interno)",
    "Invalid rate limit (1-1000 per second)": "Límite de peticiones inválido (1-1000 por segundo)",
    "Invalid IP or network: ": "IP o red inválida: ",
    "SSL certificate not found for ": "Certificado SSL no encontrado para ",
    "nginx rejected the configuration: ": "nginx rechazó la configuración: ",
    "nginx 1.25.1 or later is required for SSL (installed: {0})": "Se requiere nginx 1.25.1 o superior para SSL (instalado: {0})",
    "Remote access enabled on port {0}.": "Acceso remoto activado en el puerto {0}.",
    " Firewall: port opened for {0}.": " Firewall: puerto abierto para {0}.",
    " Firewall: could not open the port automatically ({0}); open it in Security > Firewall.": " Firewall: no se pudo abrir el puerto automáticamente ({0}); ábrelo en Seguridad > Firewall.",
    " The system firewall is not active.": " El firewall del sistema no está activo.",
    "all IPs": "todas las IPs",
    " Warning: without an IP allow-list anyone with the token can connect.": " Advertencia: sin lista blanca de IPs, cualquiera con el token puede conectarse.",
    " Warning: without SSL the token travels in plain text.": " Advertencia: sin SSL, el token viaja en texto plano.",
    "Could not query ChromaDB (is it running?)": "No se pudo consultar ChromaDB (¿está en ejecución?)",
    "Invalid database": "Base de datos inválida",
    "Invalid name: 3-512 characters [a-zA-Z0-9._-], starting and ending with an alphanumeric": "Nombre inválido: 3-512 caracteres [a-zA-Z0-9._-], empezando y terminando en alfanumérico",
    "Invalid metric": "Métrica inválida",
    "Error: ": "Error: ",
    "Collection created": "Colección creada",
    "Invalid name": "Nombre inválido",
    "Collection deleted": "Colección eliminada",
    "Database created": "Base de datos creada",
    "No data to back up": "No hay datos que respaldar",
    "Backup error: ": "Error al crear el respaldo: ",
    "Backup created: ": "Respaldo creado: ",
    "Backup not found": "Respaldo no encontrado",
    "Backup deleted": "Respaldo eliminado",
    "Invalid or unsafe backup: ": "Respaldo inválido o inseguro: ",
    "Restore error: ": "Error al restaurar: ",
    "Backup restored. Previous data moved to ": "Respaldo restaurado. Los datos anteriores se movieron a ",
    "Language saved": "Idioma guardado",
}


def _run(cmd, timeout=60):
    """Run a command (argument list, no shell) and return (rc, output)."""
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout, universal_newlines=True)
        return p.returncode, p.stdout
    except Exception as e:
        return 1, str(e)


def _write_secure(path, content, mode=0o600):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w") as f:
        f.write(content)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def _vtuple(v):
    return tuple(int(x) for x in v.split("."))


class chromadb_main:
    # NOTE: never use a request parameter called "name": aaPanel routes /plugin?action=a&name=<plugin>
    # by that key, and a POST field with the same name overrides it (the call goes to another plugin).

    # ------------------------------------------------------------------
    # Settings / i18n
    # ------------------------------------------------------------------
    def _settings(self):
        s = json.loads(json.dumps(DEFAULTS))
        if os.path.exists(SETTINGS):
            try:
                cur = json.loads(public.readFile(SETTINGS) or "{}")
                remote = cur.pop("remote", {}) or {}
                s.update(cur)
                s["remote"].update(remote)
            except Exception:
                pass
        return s

    def _save_settings(self, s):
        os.makedirs(ROOT, exist_ok=True)
        _write_secure(SETTINGS, json.dumps(s, indent=2))

    def _lang(self):
        lang = self._settings().get("lang")
        if lang in ("en", "es"):
            return lang
        try:
            pl = str(public.GetLanguage() or "").lower()
        except Exception:
            pl = ""
        return "es" if pl.startswith("es") or "spanish" in pl or "español" in pl else "en"

    def _(self, text, *args):
        if self._lang() == "es":
            text = ES.get(text, text)
        return text.format(*args) if args else text

    def _ok(self, data):
        return public.returnMsg(True, data) if isinstance(data, str) else data

    def _err(self, msg):
        return public.returnMsg(False, msg)

    def get_lang(self, get=None):
        return {"lang": self._lang(), "plugin_version": PLUGIN_VERSION}

    def set_lang(self, get):
        lang = getattr(get, "lang", "")
        if lang not in ("en", "es", ""):
            lang = ""
        s = self._settings()
        s["lang"] = lang
        self._save_settings(s)
        return self._ok(self._("Language saved"))

    # ------------------------------------------------------------------
    # Install state
    # ------------------------------------------------------------------
    def _installed(self):
        return os.path.exists(VENV + "/bin/chroma")

    def _installed_version(self):
        import glob
        for d in glob.glob(VENV + "/lib/python*/site-packages/chromadb-*.dist-info"):
            m = re.search(r"chromadb-([^-]+)\.dist-info$", d)
            if m:
                return m.group(1)
        return ""

    def _installing(self):
        if not os.path.exists(INSTALL_LOCK):
            return False
        try:
            pid = int(public.readFile(INSTALL_LOCK).strip())
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Versions (PyPI)
    # ------------------------------------------------------------------
    def _fetch_versions(self, force=False):
        """Stable chromadb releases >= MIN_VERSION, newest first. Cached 6 h. None if unreachable."""
        if not force and os.path.exists(VERSIONS_CACHE) and time.time() - os.path.getmtime(VERSIONS_CACHE) < 6 * 3600:
            try:
                return json.loads(public.readFile(VERSIONS_CACHE))
            except Exception:
                pass
        try:
            req = urllib.request.Request("https://pypi.org/pypi/chromadb/json",
                                         headers={"User-Agent": "aapanel-chromadb-plugin/" + PLUGIN_VERSION})
            with urllib.request.urlopen(req, timeout=8) as r:
                info = json.loads(r.read().decode())
        except Exception:
            return None
        out = []
        for v, files in info.get("releases", {}).items():
            if not VER_RE.match(v) or not files or all(f.get("yanked") for f in files):
                continue
            if _vtuple(v) < MIN_VERSION:
                continue
            date = min((f.get("upload_time", "") for f in files), default="")[:10]
            out.append({"version": v, "date": date})
        out.sort(key=lambda x: _vtuple(x["version"]), reverse=True)
        out = out[:40]
        try:
            os.makedirs(ROOT, exist_ok=True)
            _write_secure(VERSIONS_CACHE, json.dumps(out), 0o600)
        except Exception:
            pass
        return out

    def get_versions(self, get=None):
        force = str(getattr(get, "force", "0")) == "1" if get else False
        vs = self._fetch_versions(force)
        installed = self._installed_version() if self._installed() else ""
        return {"online": vs is not None,
                "versions": vs if vs is not None else [{"version": DEFAULT_VERSION, "date": ""}],
                "installed": installed,
                "latest": vs[0]["version"] if vs else DEFAULT_VERSION,
                "recommended": DEFAULT_VERSION}

    # ------------------------------------------------------------------
    # Config rendering (single source of truth)
    # ------------------------------------------------------------------
    def _render_yaml(self, s):
        return (
            "# Generated by the aaPanel ChromaDB plugin. Do not edit by hand.\n"
            'persist_path: "{data}"\n'
            'listen_address: "127.0.0.1"\n'
            "port: {port}\n"
            "allow_reset: false\n"
        ).format(data=DATA, port=int(s["port"]))

    def _render_unit(self, s):
        return """# Generated by the aaPanel ChromaDB plugin. Do not edit by hand.
[Unit]
Description=ChromaDB vector database (aaPanel plugin)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
Group={user}
WorkingDirectory={root}
Environment=ANONYMIZED_TELEMETRY=False
ExecStart={venv}/bin/chroma run {yaml}
Restart=always
RestartSec=5
TimeoutStopSec=30
LimitNOFILE=65535
MemoryMax={mem}

# --- Hardening ---
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
ProtectSystem=strict
ReadWritePaths={data}
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
RestrictSUIDSGID=yes
RestrictRealtime=yes
RestrictNamespaces=yes
LockPersonality=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
SystemCallArchitectures=native
UMask=0077

[Install]
WantedBy=multi-user.target
""".format(user=SERVICE_USER, root=ROOT, venv=VENV, yaml=CONFIG_YAML,
           mem=s["memory_max"], data=DATA)

    def _apply(self, restart=True):
        """Write config.yaml and the systemd unit, then (re)start the service."""
        if not self._installed():
            return self._err(self._("ChromaDB is not installed"))
        s = self._settings()
        _write_secure(CONFIG_YAML, self._render_yaml(s), 0o644)
        _write_secure(UNIT_FILE, self._render_unit(s), 0o644)
        os.makedirs(DATA, exist_ok=True)
        _run(["chown", "-R", SERVICE_USER + ":" + SERVICE_USER, DATA])
        os.chmod(DATA, 0o700)
        _run(["systemctl", "daemon-reload"])
        _run(["systemctl", "enable", UNIT_NAME])
        if restart:
            _run(["systemctl", "restart", UNIT_NAME])
            if not self._wait_healthy(s["port"]):
                return self._err(self._("The service did not respond after restarting. Check the logs."))
        return self._ok(self._("Configuration applied"))

    def _wait_healthy(self, port, seconds=30):
        for _ in range(seconds * 2):
            if self._api(port, "GET", "/api/v2/heartbeat", timeout=1)[0] == 200:
                return True
            time.sleep(0.5)
        return False

    # ------------------------------------------------------------------
    # Minimal HTTP client for the local v2 API
    # ------------------------------------------------------------------
    def _api(self, port, method, path, body=None, timeout=5):
        url = "http://127.0.0.1:{}{}".format(int(port), path)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode() or "null"
                return r.status, json.loads(raw)
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode() or "null")
            except Exception:
                return e.code, None
        except Exception as e:
            return 0, str(e)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def get_status(self, get=None):
        s = self._settings()
        installed = self._installed()
        st = {
            "installed": installed,
            "installing": self._installing(),
            "version": self._installed_version() if installed else "",
            "target_version": s["version"],
            "port": s["port"],
            "memory_max": s["memory_max"],
            "running": False,
            "healthy": False,
            "enabled": False,
            "pid": 0,
            "memory": 0,
            "since": "",
            "data_size": 0,
            "endpoint": "http://127.0.0.1:{}".format(s["port"]),
            "remote_enabled": bool(s["remote"]["enabled"]),
            "lang": self._lang(),
            "plugin_version": PLUGIN_VERSION,
        }
        if installed:
            rc, out = _run(["systemctl", "show", UNIT_NAME, "-p",
                            "ActiveState,MainPID,MemoryCurrent,ActiveEnterTimestamp,UnitFileState"])
            props = dict(l.split("=", 1) for l in out.strip().splitlines() if "=" in l)
            st["running"] = props.get("ActiveState") == "active"
            st["enabled"] = props.get("UnitFileState") == "enabled"
            st["pid"] = int(props.get("MainPID") or 0)
            mem = props.get("MemoryCurrent", "")
            st["memory"] = int(mem) if mem.isdigit() else 0
            st["since"] = props.get("ActiveEnterTimestamp", "") if st["running"] else ""
            if st["running"]:
                st["healthy"] = self._api(s["port"], "GET", "/api/v2/heartbeat", timeout=2)[0] == 200
            rc, out = _run(["du", "-sb", DATA])
            if rc == 0 and out.split():
                st["data_size"] = int(out.split()[0])
        return st

    def get_install_log(self, get=None):
        log = public.readFile(INSTALL_LOG) if os.path.exists(INSTALL_LOG) else ""
        log = ANSI_RE.sub("", log or "")
        return {"installing": self._installing(), "installed": self._installed(),
                "success": "==> DONE" in log, "log": log[-20000:]}

    # ------------------------------------------------------------------
    # Install / uninstall
    # ------------------------------------------------------------------
    def install(self, get):
        if self._installing():
            return self._err(self._("An installation is already in progress"))
        version = (getattr(get, "version", "") or DEFAULT_VERSION).strip()
        if not VER_RE.match(version):
            return self._err(self._("Invalid version"))
        if _vtuple(version) < MIN_VERSION:
            return self._err(self._("This plugin requires ChromaDB 1.0.0 or later"))
        vs = self._fetch_versions()
        if vs is not None and version not in [v["version"] for v in vs]:
            vs = self._fetch_versions(force=True)
            if vs is not None and version not in [v["version"] for v in vs]:
                return self._err(self._("Version {0} is not available on PyPI", version))
        s = self._settings()
        s["version"] = version
        self._save_settings(s)
        os.makedirs(ROOT, exist_ok=True)
        script = PLUGIN_PATH + "/scripts/setup.sh"
        with open(INSTALL_LOG, "w") as logf:
            p = subprocess.Popen(["bash", script, version], stdout=logf,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        public.writeFile(INSTALL_LOCK, str(p.pid))
        public.WriteLog("ChromaDB", "ChromaDB {} install/upgrade started".format(version))
        return self._ok(self._("Installation started"))

    def uninstall(self, get):
        if self._installing():
            return self._err(self._("An installation is in progress"))
        purge = str(getattr(get, "purge", "0")) == "1"
        self._remote_disable()
        args = ["bash", PLUGIN_PATH + "/scripts/remove.sh"] + (["--purge"] if purge else [])
        rc, out = _run(args, timeout=120)
        public.WriteLog("ChromaDB", "ChromaDB uninstalled (data {})".format("purged" if purge else "kept"))
        if rc != 0:
            return self._err(self._("Uninstall error: ") + out[-500:])
        return self._ok(self._("ChromaDB uninstalled") + ("" if purge else self._(". Data kept in ") + DATA))

    # ------------------------------------------------------------------
    # Service
    # ------------------------------------------------------------------
    def service_admin(self, get):
        action = getattr(get, "action", "")
        if action not in ("start", "stop", "restart"):
            return self._err(self._("Invalid action"))
        if not self._installed():
            return self._err(self._("ChromaDB is not installed"))
        rc, out = _run(["systemctl", action, UNIT_NAME])
        if rc != 0:
            return self._err(out[-500:])
        if action != "stop" and not self._wait_healthy(self._settings()["port"]):
            return self._err(self._("The service started but does not respond. Check the logs."))
        public.WriteLog("ChromaDB", "ChromaDB service " + action)
        return self._ok(self._({"start": "Service started", "stop": "Service stopped",
                                "restart": "Service restarted"}[action]))

    def get_logs(self, get=None):
        lines = getattr(get, "lines", 300) if get else 300
        try:
            lines = max(10, min(int(lines), 5000))
        except Exception:
            lines = 300
        rc, out = _run(["journalctl", "-u", UNIT_NAME, "-n", str(lines), "--no-pager", "-o", "short-iso"])
        return {"log": ANSI_RE.sub("", out)}

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def get_config(self, get=None):
        s = self._settings()
        r = dict(s["remote"])
        r.pop("fw_rules", None)
        return {"port": s["port"], "memory_max": s["memory_max"], "version": s["version"],
                "remote": r, "ssl_sites": self._ssl_sites(), "nginx_version": self._nginx_version(),
                "ssl_supported": self._nginx_ssl_ok()}

    def save_config(self, get):
        s = self._settings()
        try:
            port = int(getattr(get, "port", s["port"]))
        except Exception:
            return self._err(self._("Invalid port"))
        if not 1024 <= port <= 65535:
            return self._err(self._("Port must be between 1024 and 65535"))
        mem = str(getattr(get, "memory_max", s["memory_max"])).strip().upper()
        if not MEM_RE.match(mem):
            return self._err(self._("Invalid memory limit (e.g. 512M, 2G)"))
        if port != int(s["port"]) and self._port_in_use(port):
            return self._err(self._("Port {0} is already in use", port))
        if s["remote"]["enabled"] and port == int(s["remote"]["port"]):
            return self._err(self._("Port matches the remote access port"))
        s["port"], s["memory_max"] = port, mem
        self._save_settings(s)
        public.WriteLog("ChromaDB", "Config changed: port {} memory {}".format(port, mem))
        if not self._installed():
            return self._ok(self._("Saved"))
        res = self._apply(restart=True)
        if res.get("status") and s["remote"]["enabled"]:
            self._remote_write(s)
        return res

    def _port_in_use(self, port):
        rc, out = _run(["ss", "-ltnH"])
        return any(re.search(r":{}$".format(port), l.split()[3]) for l in out.splitlines() if len(l.split()) > 3)

    # ------------------------------------------------------------------
    # Remote access (nginx proxy with token) + firewall
    # ------------------------------------------------------------------
    def _ssl_sites(self):
        if not os.path.isdir(CERT_ROOT):
            return []
        return sorted(d for d in os.listdir(CERT_ROOT)
                      if os.path.exists(os.path.join(CERT_ROOT, d, "fullchain.pem"))
                      and os.path.exists(os.path.join(CERT_ROOT, d, "privkey.pem")))

    def _nginx_version(self):
        rc, out = _run([NGINX_BIN, "-v"])
        m = re.search(r"nginx/(\d+\.\d+\.\d+)", out or "")
        return m.group(1) if m else ""

    def _nginx_ssl_ok(self):
        v = self._nginx_version()
        return bool(v) and _vtuple(v) >= (1, 25, 1)   # "http2 on;" syntax

    def _render_nginx(self, s):
        r = s["remote"]
        token = r["token"]
        ssl = ""
        listen = "listen {p};\n    listen [::]:{p};".format(p=int(r["port"]))
        if r["ssl_site"]:
            cdir = os.path.join(CERT_ROOT, r["ssl_site"])
            listen = "listen {p} ssl;\n    listen [::]:{p} ssl;\n    http2 on;".format(p=int(r["port"]))
            ssl = ("ssl_certificate {c}/fullchain.pem;\n    ssl_certificate_key {c}/privkey.pem;\n"
                   "    ssl_protocols TLSv1.2 TLSv1.3;\n    ssl_session_cache shared:chromadb_ssl:5m;\n"
                   "    ssl_prefer_server_ciphers off;").format(c=cdir)
        acl = ""
        if r["whitelist"]:
            acl = "\n        ".join("allow {};".format(ip) for ip in r["whitelist"]) + "\n        deny all;"
        return """# Generated by the aaPanel ChromaDB plugin. Do not edit by hand.
limit_req_zone $binary_remote_addr zone=chromadb_rl:10m rate={rate}r/s;

server {{
    {listen}
    server_name _;
    {ssl}

    access_log /www/wwwlogs/chromadb_remote.log;
    error_log /www/wwwlogs/chromadb_remote.error.log;
    client_max_body_size 64m;
    server_tokens off;

    location / {{
        {acl}
        limit_req zone=chromadb_rl burst={burst} nodelay;
        limit_req_status 429;
        set $chromadb_auth 0;
        if ($http_authorization = "Bearer {token}") {{
            set $chromadb_auth 1;
        }}
        if ($http_x_chroma_token = "{token}") {{
            set $chromadb_auth 1;
        }}
        if ($chromadb_auth = 0) {{
            add_header WWW-Authenticate 'Bearer realm="chromadb"' always;
            return 401;
        }}
        proxy_pass http://127.0.0.1:{up};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Authorization "";
        proxy_set_header X-Chroma-Token "";
        proxy_read_timeout 300s;
    }}
}}
""".format(token=token, rate=int(r["rate"]), burst=int(r["rate"]) * 2, listen=listen,
           ssl=ssl, acl=acl, up=int(s["port"]))

    def _nginx_reload(self, new_content):
        old = public.readFile(NGINX_CONF) if os.path.exists(NGINX_CONF) else None
        if new_content is None:
            if os.path.exists(NGINX_CONF):
                os.remove(NGINX_CONF)
        else:
            _write_secure(NGINX_CONF, new_content, 0o600)
        rc, out = _run([NGINX_BIN, "-t"])
        if rc != 0:
            if old is None:
                if os.path.exists(NGINX_CONF):
                    os.remove(NGINX_CONF)
            else:
                _write_secure(NGINX_CONF, old, 0o600)
            return False, out
        _run(["/etc/init.d/nginx", "reload"])
        return True, ""

    def _remote_write(self, s):
        return self._nginx_reload(self._render_nginx(s))

    # --- firewall (aaPanel firewall module) ---
    def _fw(self):
        sys.path.insert(0, BASE_PATH + "/class_v2/")
        if BASE_PATH not in sys.path:
            sys.path.insert(0, BASE_PATH)
        from firewallModelV2.comModel import main as fw_main
        return fw_main()

    def _fw_rule(self, fw, operation, port, address):
        a = public.dict_obj()
        a.operation, a.protocol, a.port, a.address = operation, "tcp", str(port), address
        a.strategy, a.chain, a.reload, a.brief = "accept", "INPUT", "1", FW_BRIEF
        res = fw.set_port_rule(a)
        if isinstance(res, dict):
            st = res.get("status")
            ok = st is True or st == 0
            msg = res.get("msg") or res.get("message")
            if isinstance(msg, dict):
                msg = msg.get("result") or json.dumps(msg)
            return ok, str(msg or "")
        return False, str(res)

    def _fw_close(self, s):
        """Remove the firewall rules this plugin created. Returns nothing; best effort."""
        rules = s["remote"].get("fw_rules") or []
        if rules:
            try:
                fw = self._fw()
                for rule in rules:
                    self._fw_rule(fw, "remove", rule["port"], rule["address"])
            except Exception:
                pass
        s["remote"]["fw_rules"] = []

    def _fw_open(self, s):
        """Open the remote port for the allow-list (or everyone). Returns a message suffix."""
        r = s["remote"]
        try:
            fw = self._fw()
            if not fw.get_firewall_status():
                return self._(" The system firewall is not active.")
            addrs = r["whitelist"] or ["all"]
            added = []
            for addr in addrs:
                ok, msg = self._fw_rule(fw, "add", r["port"], addr)
                if ok or "already exists" in msg:
                    added.append({"port": int(r["port"]), "address": addr})
                else:
                    r["fw_rules"] = added
                    return self._(" Firewall: could not open the port automatically ({0}); open it in Security > Firewall.", msg)
            r["fw_rules"] = added
            return self._(" Firewall: port opened for {0}.",
                          ", ".join(r["whitelist"]) if r["whitelist"] else self._("all IPs"))
        except Exception as e:
            return self._(" Firewall: could not open the port automatically ({0}); open it in Security > Firewall.", e)

    def _remote_disable(self):
        s = self._settings()
        self._fw_close(s)
        s["remote"]["enabled"] = False
        self._save_settings(s)
        if os.path.exists(NGINX_CONF):
            self._nginx_reload(None)
            # nginx workers release the listening socket asynchronously after a reload
            for _ in range(20):
                if not self._port_in_use(int(s["remote"]["port"])):
                    break
                time.sleep(0.5)

    def save_remote(self, get):
        s = self._settings()
        r = s["remote"]
        enabled = str(getattr(get, "enabled", "0")) == "1"
        if not enabled:
            self._remote_disable()
            public.WriteLog("ChromaDB", "Remote access disabled")
            return self._ok(self._("Remote access disabled"))
        if not self._installed():
            return self._err(self._("Install ChromaDB first"))
        try:
            port = int(getattr(get, "port", r["port"]))
            rate = int(getattr(get, "rate", r["rate"]))
        except Exception:
            return self._err(self._("Invalid numeric values"))
        if not 1024 <= port <= 65535 or port == int(s["port"]):
            return self._err(self._("Invalid remote port (1024-65535 and different from the internal port)"))
        if not 1 <= rate <= 1000:
            return self._err(self._("Invalid rate limit (1-1000 per second)"))
        if (not r["enabled"] or port != int(r["port"])) and self._port_in_use(port):
            return self._err(self._("Port {0} is already in use", port))
        wl = []
        for item in re.split(r"[\s,;]+", str(getattr(get, "whitelist", "")).strip()):
            if not item:
                continue
            try:
                net = ipaddress.ip_network(item, strict=False)
                wl.append(str(net.network_address) if net.num_addresses == 1 else str(net))
            except ValueError:
                return self._err(self._("Invalid IP or network: ") + item)
        site = str(getattr(get, "ssl_site", "")).strip()
        if site and site not in self._ssl_sites():
            return self._err(self._("SSL certificate not found for ") + site)
        if site and not self._nginx_ssl_ok():
            return self._err(self._("nginx 1.25.1 or later is required for SSL (installed: {0})", self._nginx_version() or "?"))
        if not r["token"] or str(getattr(get, "regen_token", "0")) == "1":
            r["token"] = secrets.token_hex(32)
        # Close previous firewall rules; reopen with the new port/allow-list
        self._fw_close(s)
        r.update({"enabled": True, "port": port, "rate": rate, "whitelist": wl, "ssl_site": site})
        ok, out = self._remote_write(s)
        if not ok:
            self._save_settings(s)
            return self._err(self._("nginx rejected the configuration: ") + out[-800:])
        msg = self._("Remote access enabled on port {0}.", port) + self._fw_open(s)
        self._save_settings(s)
        public.WriteLog("ChromaDB", "Remote access enabled on port {}{}".format(port, " (SSL)" if site else ""))
        if not wl:
            msg += self._(" Warning: without an IP allow-list anyone with the token can connect.")
        if not site:
            msg += self._(" Warning: without SSL the token travels in plain text.")
        return self._ok(msg)

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------
    def _db_base(self, db):
        return "/api/v2/tenants/{}/databases/{}".format(TENANT, db)

    def get_databases(self, get=None):
        s = self._settings()
        code, data = self._api(s["port"], "GET", "/api/v2/tenants/{}/databases".format(TENANT))
        if code != 200:
            return self._err(self._("Could not query ChromaDB (is it running?)"))
        return [d.get("name") for d in data]

    def get_collections(self, get):
        s = self._settings()
        db = getattr(get, "database", "default_database") or "default_database"
        if not NAME_RE.match(db):
            return self._err(self._("Invalid database"))
        code, data = self._api(s["port"], "GET", self._db_base(db) + "/collections?limit=1000")
        if code != 200:
            return self._err(self._("Could not query ChromaDB (is it running?)"))
        out = []
        for c in data or []:
            cnt_code, cnt = self._api(s["port"], "GET", self._db_base(db) + "/collections/{}/count".format(c["id"]))
            cfg = c.get("configuration_json") or c.get("configuration") or {}
            space = ""
            if isinstance(cfg, dict):
                hnsw = cfg.get("hnsw") or {}
                space = hnsw.get("space", "") if isinstance(hnsw, dict) else ""
            out.append({"id": c["id"], "name": c["name"], "count": cnt if cnt_code == 200 else "?",
                        "dimension": c.get("dimension"), "metadata": c.get("metadata") or {},
                        "space": space})
        return out

    def create_collection(self, get):
        s = self._settings()
        db = getattr(get, "database", "default_database") or "default_database"
        name = str(getattr(get, "collection", "")).strip()
        space = getattr(get, "space", "cosine")
        if not NAME_RE.match(db) or not NAME_RE.match(name):
            return self._err(self._("Invalid name: 3-512 characters [a-zA-Z0-9._-], starting and ending with an alphanumeric"))
        if space not in ("cosine", "l2", "ip"):
            return self._err(self._("Invalid metric"))
        body = {"name": name, "configuration": {"hnsw": {"space": space}}}
        code, data = self._api(s["port"], "POST", self._db_base(db) + "/collections", body)
        if code != 200:
            return self._err(self._("Error: ") + str(data))
        public.WriteLog("ChromaDB", "Collection created: {}/{}".format(db, name))
        return self._ok(self._("Collection created"))

    def delete_collection(self, get):
        s = self._settings()
        db = getattr(get, "database", "default_database") or "default_database"
        name = str(getattr(get, "collection", "")).strip()
        if not NAME_RE.match(db) or not NAME_RE.match(name):
            return self._err(self._("Invalid name"))
        code, data = self._api(s["port"], "DELETE", self._db_base(db) + "/collections/" + name)
        if code != 200:
            return self._err(self._("Error: ") + str(data))
        public.WriteLog("ChromaDB", "Collection deleted: {}/{}".format(db, name))
        return self._ok(self._("Collection deleted"))

    def create_database(self, get):
        s = self._settings()
        name = str(getattr(get, "db_name", "")).strip()
        if not NAME_RE.match(name):
            return self._err(self._("Invalid name"))
        code, data = self._api(s["port"], "POST", "/api/v2/tenants/{}/databases".format(TENANT), {"name": name})
        if code != 200:
            return self._err(self._("Error: ") + str(data))
        public.WriteLog("ChromaDB", "Database created: " + name)
        return self._ok(self._("Database created"))

    # ------------------------------------------------------------------
    # Backups
    # ------------------------------------------------------------------
    def get_backups(self, get=None):
        if not os.path.isdir(BACKUP_DIR):
            return []
        out = []
        for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if BACKUP_RE.match(f):
                p = os.path.join(BACKUP_DIR, f)
                out.append({"name": f, "path": p, "size": os.path.getsize(p),
                            "time": int(os.path.getmtime(p))})
        return out

    def create_backup(self, get=None):
        if not self._installed() or not os.path.isdir(DATA):
            return self._err(self._("No data to back up"))
        os.makedirs(BACKUP_DIR, mode=0o700, exist_ok=True)
        name = time.strftime("chromadb_%Y%m%d_%H%M%S.tar.gz")
        path = os.path.join(BACKUP_DIR, name)
        was_running = self.get_status()["running"]
        # Brief stop for a consistent copy (SQLite + HNSW segments)
        if was_running:
            _run(["systemctl", "stop", UNIT_NAME])
        try:
            with tarfile.open(path, "w:gz") as t:
                t.add(DATA, arcname="data")
            os.chmod(path, 0o600)
        except Exception as e:
            if os.path.exists(path):
                os.remove(path)
            return self._err(self._("Backup error: ") + str(e))
        finally:
            if was_running:
                _run(["systemctl", "start", UNIT_NAME])
                self._wait_healthy(self._settings()["port"])
        public.WriteLog("ChromaDB", "Backup created: " + name)
        return self._ok(self._("Backup created: ") + name)

    def _backup_path(self, get):
        name = os.path.basename(str(getattr(get, "file", "")))
        if not BACKUP_RE.match(name):
            return None
        p = os.path.join(BACKUP_DIR, name)
        return p if os.path.isfile(p) else None

    def delete_backup(self, get):
        p = self._backup_path(get)
        if not p:
            return self._err(self._("Backup not found"))
        os.remove(p)
        public.WriteLog("ChromaDB", "Backup deleted: " + os.path.basename(p))
        return self._ok(self._("Backup deleted"))

    def restore_backup(self, get):
        p = self._backup_path(get)
        if not p:
            return self._err(self._("Backup not found"))
        if not self._installed():
            return self._err(self._("ChromaDB is not installed"))
        # Validate archive contents before touching anything (path traversal, links, devices)
        with tarfile.open(p, "r:gz") as t:
            for m in t.getmembers():
                n = os.path.normpath(m.name)
                if n.startswith("/") or n.startswith("..") or not (n == "data" or n.startswith("data/")) \
                        or m.issym() or m.islnk() or m.isdev():
                    return self._err(self._("Invalid or unsafe backup: ") + m.name)
        _run(["systemctl", "stop", UNIT_NAME])
        stash = DATA + ".before_restore_" + time.strftime("%Y%m%d_%H%M%S")
        tmp = ROOT + "/.restore_tmp"
        try:
            shutil.rmtree(tmp, ignore_errors=True)
            os.makedirs(tmp, mode=0o700)
            with tarfile.open(p, "r:gz") as t:
                if sys.version_info >= (3, 12):
                    t.extractall(tmp, filter="data")
                else:
                    t.extractall(tmp)
            if os.path.isdir(DATA):
                os.rename(DATA, stash)
            os.rename(tmp + "/data", DATA)
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception as e:
            if not os.path.isdir(DATA) and os.path.isdir(stash):
                os.rename(stash, DATA)
            _run(["systemctl", "start", UNIT_NAME])
            return self._err(self._("Restore error: ") + str(e))
        res = self._apply(restart=True)
        public.WriteLog("ChromaDB", "Backup restored: " + os.path.basename(p))
        if not res.get("status"):
            return res
        return self._ok(self._("Backup restored. Previous data moved to ") + stash)

    # ------------------------------------------------------------------
    # CLI (used by scripts/setup.sh and cron backups)
    # ------------------------------------------------------------------
    def cli(self, argv):
        cmd = argv[1] if len(argv) > 1 else ""
        if cmd == "apply":
            res = self._apply(restart=True)
        elif cmd == "backup":
            res = self.create_backup()
        else:
            print("usage: chromadb_main.py apply|backup")
            return 2
        print(res.get("msg", res))
        return 0 if res.get("status") else 1


if __name__ == "__main__":
    sys.exit(chromadb_main().cli(sys.argv))
