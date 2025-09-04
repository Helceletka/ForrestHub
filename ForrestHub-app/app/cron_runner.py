import os
import json
import logging
from pathlib import Path

import js2py
import requests
from eventlet import sleep, Timeout

_log = logging.getLogger(__name__)


def _discover_game_dirs(app) -> list[Path]:
    """Find game directories (prefer live), ignore dot-prefixed."""
    dirs: list[Path] = []
    for key in ("GAMES_FOLDER_LIVE", "GAMES_FOLDER"):
        base = app.config.get(key)
        if not base:
            continue
        base_path = Path(base)
        if not base_path.exists():
            continue
        for child in base_path.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                dirs.append(child)
    return dirs


def _build_js_prelude() -> str:
    """
    Minimal standard library for cron.js in ES5 style.
    Provides:
      - console.log / console.error
      - ENV (object with FH_* vars)
      - httpGet(url, headers?)
      - httpPost(url, body?, headers?)
      - getVar(project, key, defaultValue?)
      - setVar(project, key, value)
      - addRecord(project, arrayName, value)
      - removeRecord(project, arrayName, recordId)
    NOTE: Use sync helpers above (no fetch/Promise/await).
    """
    return """
// --- Console ---
if (typeof console === 'undefined') { console = {}; }
console.log   = function(){ __py_log([].slice.call(arguments).join(" ")); };
console.error = function(){ __py_err([].slice.call(arguments).join(" ")); };

// --- Env ---
var ENV = __py_env();  // plain object with FH_* keys

// --- HTTP (sync) ---
function httpGet(url, headers)  { return __py_http_get(String(url), headers || {}); }
function httpPost(url, body, headers) { return __py_http_post(String(url), (typeof body==='undefined' ? '' : body), headers || {}); }

// --- ForrestHub DB helpers (sync) ---
function getVar(project, key, defaultValue) { return __py_get_var(String(project), String(key), typeof defaultValue==='undefined' ? null : defaultValue); }
function setVar(project, key, value)        { return __py_set_var(String(project), String(key), value); }
function addRecord(project, arrayName, value){ return __py_arr_add(String(project), String(arrayName), value); }
function removeRecord(project, arrayName, recordId){ return __py_arr_remove(String(project), String(arrayName), String(recordId)); }
"""


def _make_js_context(app, game_name: str, timeout_sec: int):
    """
    Create a Js2Py sandbox and bridge a few Python helpers.
    """
    from app.init import db  # lazy import to avoid init cycles

    base_url = f"http://{app.config['HOST']}:{app.config['PORT']}"

    def _env():
        return {
            "FH_HOST": str(app.config["HOST"]),
            "FH_PORT": str(app.config["PORT"]),
            "FH_BASE_URL": base_url,
            "FH_EXECUTABLE_DIR": str(app.config["EXECUTABLE_DIR"]),
            "FH_DATA_DIR": str(app.config["DATA_DIR"]),
            "FH_GAMES_DIR": str(app.config["GAMES_FOLDER"]),
            "FH_GAMES_DIR_LIVE": str(app.config["GAMES_FOLDER_LIVE"]),
            "FH_GAME_NAME": game_name,
            "FH_CRON_TIMEOUT_SEC": str(timeout_sec),
        }

    def _log_py(msg):
        _log.info("[cron.js][%s] %s", game_name, str(msg))

    def _err_py(msg):
        _log.error("[cron.js][%s] %s", game_name, str(msg))

    def _http_get(url: str, headers: dict):
        try:
            r = requests.get(url, headers=headers or {}, timeout=max(1, timeout_sec - 1))
            return {"status": r.status_code, "text": r.text}
        except Exception as e:
            return {"status": 0, "text": f"ERROR: {e}"}

    def _to_py(obj):
        """Best-effort convert Js2Py values to native Python."""
        try:
            # Most Js2Py values implement .to_python()
            return obj.to_python()
        except Exception:
            return obj

    def _to_str(obj) -> str:
        v = _to_py(obj)
        return v if isinstance(v, str) else str(v)


    def _http_post(url: str, body, headers: dict):
        try:
            data = _to_py(body)
            # Accept JS object/array or string:
            if isinstance(data, (dict, list)):
                data = json.dumps(data)
                headers = dict(headers or {})
                headers.setdefault("content-type", "application/json")
            r = requests.post(url, data=data, headers=headers or {}, timeout=max(1, timeout_sec - 1))
            return {"status": r.status_code, "text": r.text}
        except Exception as e:
            return {"status": 0, "text": f"ERROR: {e}"}

    # DB bridges (no HTTP; direct):
    def _get_var(project: str, key: str, default_value=None):
        return db.var_key_get(_to_str(project), _to_str(key), _to_py(default_value))

    def _set_var(project: str, key: str, value):
        db.var_key_set(_to_str(project), _to_str(key), _to_py(value))
        return True

    def _arr_add(project: str, array_name: str, value):
        db.array_add_record(_to_str(project), _to_str(array_name), _to_py(value))
        return True

    def _arr_remove(project: str, array_name: str, record_id: str):
        return bool(db.array_remove_record(_to_str(project), _to_str(array_name), _to_str(record_id)))

    ctx = js2py.EvalJs({})
    # inject bridges:
    ctx.__py_env = _env
    ctx.__py_log = _log_py
    ctx.__py_err = _err_py
    ctx.__py_http_get = _http_get
    ctx.__py_http_post = _http_post
    ctx.__py_get_var = _get_var
    ctx.__py_set_var = _set_var
    ctx.__py_arr_add = _arr_add
    ctx.__py_arr_remove = _arr_remove

    return ctx


def _run_js_file(app, script_path: Path, timeout_sec: int):
    """Execute a cron.js file with a hard timeout."""
    game_name = script_path.parent.name
    code = script_path.read_text(encoding="utf-8")

    ctx = _make_js_context(app, game_name, timeout_sec)
    prelude = _build_js_prelude()

    # Execute with timeout to avoid runaway scripts
    try:
        with Timeout(timeout_sec, False):
            ctx.execute(prelude + "\n" + code)
    except Exception as e:
        _log.exception("Error executing cron.js in '%s': %s", game_name, e)


def start_cron_scheduler(app) -> None:
    """
    Background loop:
      - Every FH_CRON_INTERVAL_SEC (default 10s)
      - For each game dir, if cron.js exists, execute it with Js2Py.
    """
    print("Starting cron scheduler...")
    interval = int(os.getenv("FH_CRON_INTERVAL_SEC", "10"))
    timeout = int(os.getenv("FH_CRON_TIMEOUT_SEC", "8"))

    _log.info("Starting JS cron scheduler (Js2Py): interval=%ss, timeout/run=%ss", interval, timeout)

    with app.app_context():
        while True:
            try:
                for game_dir in _discover_game_dirs(app):
                    print(game_dir)
                    cron_file = game_dir / "cron.js"
                    if cron_file.exists():
                        _run_js_file(app, cron_file, timeout)
            except Exception as loop_err:
                _log.exception("cron scheduler loop error: %s", loop_err)
            sleep(interval)
