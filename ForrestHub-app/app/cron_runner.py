import os
import json
import logging
from pathlib import Path

import js2py
import requests
from eventlet import sleep, Timeout

_log = logging.getLogger(__name__)


# --------------------- Utils ---------------------
def _deep_to_py(obj):
    """
    Convert Js2Py values to native Python recursively.
    Handles:
      - Js2Py primitives/wrappers via .to_python()
      - JsObjectWrapper-like via _obj
      - dict/list/tuple/set
    Falls back to str() for unknowns to avoid crashes.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # Js2Py values (PyJs* etc.)
    if hasattr(obj, "to_python") and callable(getattr(obj, "to_python")):
        try:
            return _deep_to_py(obj.to_python())
        except Exception:
            pass

    # JsObjectWrapper-like
    inner = getattr(obj, "_obj", None)
    if inner is not None and inner is not obj:
        try:
            return _deep_to_py(inner)
        except Exception:
            pass

    if isinstance(obj, dict):
        return {str(k): _deep_to_py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_deep_to_py(v) for v in obj]

    return str(obj)


def _to_str(obj) -> str:
    v = _deep_to_py(obj)
    return v if isinstance(v, str) else str(v)


# --------------------- Game discovery ---------------------
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


# --------------------- JS prelude ---------------------
def _build_js_prelude() -> str:
    """
    Minimal standard lib for cron.js (ES5). No sockets/listeners.
    Provides:
      - console.log / console.error
      - ENV (FH_* vars)
      - httpGet/httpPost
      - Raw DB helpers (getVar/setVar/addRecord/removeRecord etc.)
      - ForrestHubLib class with the same data API as in the browser
    Note: any data coming from Python is deep-cloned (JSON) to avoid
    JsObjectWrapper references being passed back.
    """
    return r"""
// -------- Console --------
if (typeof console === 'undefined') { console = {}; }
console.log   = function(){ __py_log([].slice.call(arguments).join(" ")); };
console.error = function(){ __py_err([].slice.call(arguments).join(" ")); };

// -------- ENV --------
var ENV = __py_env();  // plain object with FH_* keys

// -------- Helpers --------
function cloneJSON(x){ return JSON.parse(JSON.stringify(x)); }

// -------- HTTP (sync) --------
function httpGet(url, headers)  { return __py_http_get(String(url), headers || {}); }
function httpPost(url, body, headers) {
  return __py_http_post(String(url), (typeof body==='undefined' ? '' : body), headers || {});
}

// -------- Raw DB bridge (sync) --------
function getVar(project, key, defaultValue)    { return __py_get_var(String(project), String(key), (typeof defaultValue==='undefined'? null : defaultValue)); }
function setVar(project, key, value)           { return __py_set_var(String(project), String(key), value); }
function varExists(project, key)               { return __py_var_exist(String(project), String(key)); }
function varDelete(project, key)               { return __py_var_delete(String(project), String(key)); }

function addRecord(project, arrayName, value)  { return __py_arr_add(String(project), String(arrayName), value); }
function removeRecord(project, arrayName, id)  { return __py_arr_remove(String(project), String(arrayName), String(id)); }
function updateRecord(project, arrayName, id, value) { return __py_arr_update(String(project), String(arrayName), String(id), value); }
function getAllRecords(project, arrayName)     { return cloneJSON(__py_arr_get_all(String(project), String(arrayName))); }
function clearRecords(project, arrayName)      { return __py_arr_clear(String(project), String(arrayName)); }
function listProjects()                        { return cloneJSON(__py_arr_list_projects()); }

function dbAll()    { return cloneJSON(__py_db_all()); }
function dbClear()  { __py_db_clear(); }

// -------- Minimal ForrestHubLib (no sockets/listeners) --------
function ForrestHubLib(isGame, url) {
  if (ForrestHubLib.instance) return ForrestHubLib.instance;

  this.RUNNING = "running";
  this.PAUSED  = "paused";
  this.STOPPED = "stopped";

  this.project    = ENV.FH_GAME_NAME || "global";
  this.isGamePage = !!isGame;

  ForrestHubLib.instance = this;
  return this;
}

ForrestHubLib.getInstance = function(isGame, url) {
  if (!ForrestHubLib.instance) {
    ForrestHubLib.instance = new ForrestHubLib(isGame, url);
  }
  return ForrestHubLib.instance;
};

// ---- Project helpers
ForrestHubLib.prototype.dbSetProject = function(project) {
  this.project = String(project || "");
};
ForrestHubLib.prototype.dbResolveProjectName = function(projectOverride) {
  return String(projectOverride || this.project || "global");
};

// ---- Whole DB
ForrestHubLib.prototype.dbFetchAllData = function() {
  return dbAll() || {};
};
ForrestHubLib.prototype.dbClearAllData = function() {
  dbClear();
};

// ---- VAR
ForrestHubLib.prototype.dbVarSetKey = function(key, value, projectOverride) {
  if (!key || typeof key !== "string") throw new Error("dbVarSetKey: key must be non-empty string");
  var project = this.dbResolveProjectName(projectOverride);
  setVar(project, key, value);
};
ForrestHubLib.prototype.dbVarGetKey = function(key, projectOverride) {
  if (!key || typeof key !== "string") throw new Error("dbVarGetKey: key must be non-empty string");
  var project = this.dbResolveProjectName(projectOverride);
  return getVar(project, key, null);
};
ForrestHubLib.prototype.dbVarKeyExists = function(key, projectOverride) {
  if (!key || typeof key !== "string") throw new Error("dbVarKeyExists: key must be non-empty string");
  var project = this.dbResolveProjectName(projectOverride);
  return !!varExists(project, key);
};
ForrestHubLib.prototype.dbVarDeleteKey = function(key, projectOverride) {
  if (!key || typeof key !== "string") throw new Error("dbVarDeleteKey: key must be non-empty string");
  var project = this.dbResolveProjectName(projectOverride);
  varDelete(project, key);
};

// ---- ARRAY
ForrestHubLib.prototype.dbArrayAddRecord = function(arrayName, value, projectOverride) {
  if (!arrayName || typeof arrayName !== "string") throw new Error("dbArrayAddRecord: arrayName must be non-empty string");
  var project = this.dbResolveProjectName(projectOverride);
  addRecord(project, arrayName, value);
};
ForrestHubLib.prototype.dbArrayRemoveRecord = function(arrayName, recordId, projectOverride) {
  if (!arrayName || typeof arrayName !== "string") throw new Error("dbArrayRemoveRecord: arrayName must be non-empty string");
  if (!recordId || typeof recordId !== "string") throw new Error("dbArrayRemoveRecord: recordId must be non-empty string");
  var project = this.dbResolveProjectName(projectOverride);
  removeRecord(project, arrayName, recordId);
};
ForrestHubLib.prototype.dbArrayUpdateRecord = function(arrayName, recordId, value, projectOverride) {
  if (!arrayName || typeof arrayName !== "string") throw new Error("dbArrayUpdateRecord: arrayName must be non-empty string");
  if (!recordId || typeof recordId !== "string") throw new Error("dbArrayUpdateRecord: recordId must be non-empty string");
  var project = this.dbResolveProjectName(projectOverride);
  updateRecord(project, arrayName, recordId, value);
};
ForrestHubLib.prototype.dbArrayFetchAllRecords = function(arrayName, projectOverride) {
  if (!arrayName || typeof arrayName !== "string") throw new Error("dbArrayFetchAllRecords: arrayName must be non-empty string");
  var project = this.dbResolveProjectName(projectOverride);
  return getAllRecords(project, arrayName) || {};
};
ForrestHubLib.prototype.dbArrayClearRecords = function(arrayName, projectOverride) {
  if (!arrayName || typeof arrayName !== "string") throw new Error("dbArrayClearRecords: arrayName must be non-empty string");
  var project = this.dbResolveProjectName(projectOverride);
  clearRecords(project, arrayName);
};
ForrestHubLib.prototype.dbArrayFetchProjects = function() {
  return listProjects() || [];
};

// ---- small helpers
ForrestHubLib.prototype.logDebug = function(msg){ console.log("[ForrestHubLib] " + msg); };

// ---- Create singleton for convenience
var forrestHubLib = ForrestHubLib.getInstance(true);
"""


# --------------------- JS context ---------------------
def _make_js_context(app, game_name: str, timeout_sec: int):
    """
    Create a Js2Py sandbox and bridge Python helpers.
    """
    from app.init import db  # lazy import (avoid init cycles)

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
            hdrs = _deep_to_py(headers or {})
            r = requests.get(_to_str(url), headers=dict(hdrs or {}), timeout=max(1, timeout_sec - 1))
            return {"status": r.status_code, "text": r.text}
        except Exception as e:
            return {"status": 0, "text": f"ERROR: {e}"}

    def _http_post(url: str, body, headers: dict):
        try:
            data = _deep_to_py(body)
            hdrs = _deep_to_py(headers or {})
            if isinstance(data, (dict, list)):
                data = json.dumps(data)
                hdrs = dict(hdrs or {})
                hdrs.setdefault("content-type", "application/json")
            r = requests.post(_to_str(url), data=data, headers=hdrs, timeout=max(1, timeout_sec - 1))
            return {"status": r.status_code, "text": r.text}
        except Exception as e:
            return {"status": 0, "text": f"ERROR: {e}"}

    # ----- DB bridges (direct; no HTTP) -----
    def _get_var(project, key, default_value=None):
        return db.var_key_get(_to_str(project), _to_str(key), _deep_to_py(default_value))

    def _set_var(project, key, value):
        db.var_key_set(_to_str(project), _to_str(key), _deep_to_py(value))
        return True

    def _var_exist(project, key):
        return bool(db.var_key_exists(_to_str(project), _to_str(key)))

    def _var_delete(project, key):
        return bool(db.var_key_delete(_to_str(project), _to_str(key)))

    def _arr_add(project, array_name, value):
        db.array_add_record(_to_str(project), _to_str(array_name), _deep_to_py(value))
        return True

    def _arr_remove(project, array_name, record_id):
        return bool(db.array_remove_record(_to_str(project), _to_str(array_name), _to_str(record_id)))

    def _arr_update(project, array_name, record_id, value):
        return bool(db.array_update_record(_to_str(project), _to_str(array_name), _to_str(record_id), _deep_to_py(value)))

    def _arr_get_all(project, array_name):
        # Return raw Python dict; JS prelude clones it to avoid wrappers.
        return db.array_get_all_records(_to_str(project), _to_str(array_name)) or {}

    def _arr_clear(project, array_name):
        db.array_clear_records(_to_str(project), _to_str(array_name))
        return True

    def _arr_list_projects():
        return db.array_list_projects()

    def _db_all():
        return db.get_all_data() or {}

    def _db_clear():
        db.clear_data()
        return True

    ctx = js2py.EvalJs({})

    # inject bridges:
    ctx.__py_env = _env
    ctx.__py_log = _log_py
    ctx.__py_err = _err_py
    ctx.__py_http_get = _http_get
    ctx.__py_http_post = _http_post

    ctx.__py_get_var = _get_var
    ctx.__py_set_var = _set_var
    ctx.__py_var_exist = _var_exist
    ctx.__py_var_delete = _var_delete

    ctx.__py_arr_add = _arr_add
    ctx.__py_arr_remove = _arr_remove
    ctx.__py_arr_update = _arr_update
    ctx.__py_arr_get_all = _arr_get_all
    ctx.__py_arr_clear = _arr_clear
    ctx.__py_arr_list_projects = _arr_list_projects

    ctx.__py_db_all = _db_all
    ctx.__py_db_clear = _db_clear

    return ctx


# --------------------- Runner ---------------------
def _run_js_file(app, script_path: Path, timeout_sec: int):
    """Execute a cron.js file with a hard timeout."""
    game_name = script_path.parent.name
    code = script_path.read_text(encoding="utf-8")

    ctx = _make_js_context(app, game_name, timeout_sec)
    prelude = _build_js_prelude()

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
    interval = int(os.getenv("FH_CRON_INTERVAL_SEC", "10"))
    timeout = int(os.getenv("FH_CRON_TIMEOUT_SEC", "8"))

    _log.info("Starting JS cron scheduler (Js2Py): interval=%ss, timeout/run=%ss", interval, timeout)

    with app.app_context():
        while True:
            try:
                for game_dir in _discover_game_dirs(app):
                    cron_file = game_dir / "cron.js"
                    if cron_file.exists():
                        _run_js_file(app, cron_file, timeout)
            except Exception as loop_err:
                _log.exception("cron scheduler loop error: %s", loop_err)
            sleep(interval)
