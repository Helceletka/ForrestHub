from pathlib import Path
from flask_socketio import emit
from app.games import copy_default_game
from app.init import socketio, db

from flask import (
    Blueprint,
    current_app,
)

socketio_bp = Blueprint("socketio", __name__)
connected_clients = 0
connected_admins = 0

game_status = "running"  # default; DB will override if set
try:
    _db_status = db.var_key_get("global", "game_status", game_status)
    if _db_status:
        game_status = _db_status
except Exception:
    pass

################## Admin Config ############################
@socketio.on("send_admin_message")
def handle_admin_message(message):
    emit("admin_messages", message, broadcast=True)


@socketio.on("connect")
def handle_connect():
    global connected_clients
    connected_clients += 1
    emit("update_clients", {"count": connected_clients}, broadcast=True)


@socketio.on("disconnect")
def handle_disconnect():
    global connected_clients
    connected_clients -= 1
    emit("update_clients", {"count": connected_clients}, broadcast=True)


@socketio.on("game_status_get")
def handle_game_status(_payload):
    # Serve the current (DB-backed) status
    current = db.var_key_get("global", "game_status", game_status)
    emit("game_status", current)


@socketio.on("game_status_set")
def handle_game_status_set(status: str):
    # Normalize + persist
    s = (status or "").strip().lower()
    if s not in ("running", "paused", "stopped"):
        s = "paused"  # fallback on invalid inputs
    global game_status
    game_status = s
    db.var_key_set("global", "game_status", s)
    emit("game_status", s, broadcast=True)

################## Edit mode ############################

@socketio.on("edit_mode_get")
def handle_game_status(demo):
    emit("edit_mode", db.edit_mode_is_on())


@socketio.on("edit_mode_set")
def handle_game_status_set(edit_mode_on: bool):
    db.set_edit_mode(edit_mode_on)
    emit("edit_mode", edit_mode_on, broadcast=True)
    if edit_mode_on:
        return copy_default_game()

################## Admin Access ############################


@socketio.on("db_get_all_data")
def handle_get_all_data(data) -> dict:
    return {"status": "ok", "data": db.get_all_data()}


@socketio.on("db_delete_all_data")
def handle_delete_all_data(data) -> dict:
    db.clear_data()
    return {"status": "ok"}


################## VAR ############################

@socketio.on("var_key_set")
def handle_key_set(json: dict):
    project = json.get("project")
    key = json.get("key")
    value = json.get("value")
    db.var_key_set(project, key, value)
    return {"status": "ok"}


@socketio.on("var_key_exist")
def handle_key_exists(json: dict) -> dict:
    project = json.get("project")
    key = json.get("key")
    return {"status": "ok", "exists": db.var_key_exists(project, key)}


@socketio.on("var_key_get")
def handle_key_get(json: dict) -> dict:
    project = json.get("project")
    key = json.get("key")
    default_value = json.get("defaultValue", "")
    return {"status": "ok", "data": db.var_key_get(project, key, default_value)}


@socketio.on("var_key_delete")
def handle_key_delete(json: dict) -> dict:
    project = json.get("project")
    key = json.get("key")
    db.var_key_delete(project, key)
    return {"status": "ok"}


################## Array ############################

@socketio.on("array_add_record")
def handle_array_add_record(json: dict) -> dict:
    project = json.get("project")
    array_name = json.get("arrayName")
    value = json.get("value")
    db.array_add_record(project, array_name, value)
    return {"status": "ok"}


@socketio.on("array_remove_record")
def handle_array_remove_record(json: dict) -> dict:
    project = json.get("project")
    array_name = json.get("arrayName")
    record_id = json.get("recordId")
    db.array_remove_record(project, array_name, record_id)
    return {"status": "ok"}


@socketio.on("array_update_record")
def handle_array_update_record(json: dict) -> dict:
    project = json.get("project")
    array_name = json.get("arrayName")
    record_id = json.get("recordId")
    value = json.get("value")
    db.array_update_record(project, array_name, record_id, value)
    return {"status": "ok"}

@socketio.on("array_get_all_records")
def handle_array_get_all_records(json: dict) -> dict:
    project = json.get("project")
    array_name = json.get("arrayName")
    return {"status": "ok", "data": db.array_get_all_records(project, array_name)}


@socketio.on("array_get_record_id")
def handle_array_get_record(json: dict) -> dict:
    project = json.get("project")
    array_name = json.get("arrayName")
    record_id = json.get("recordId")
    return {"status": "ok", "data": db.array_get_record_id(project, array_name, record_id)}

@socketio.on("array_clear_records")
def handle_array_clear_records(json: dict) -> dict:
    project = json.get("project")
    array_name = json.get("arrayName")
    db.array_clear_records(project, array_name)
    return {"status": "ok"}


@socketio.on("array_list_projects")
def handle_get_all_projects(json: dict) -> dict:
    return {"status": "ok", "data": db.array_list_projects()}


################## Edit game ############################

@socketio.on("add_new_game")
def handle_add_new_game(game_name: str) -> dict:
    game_folder = Path(current_app.config.get("GAMES_FOLDER_LIVE"))
    if not game_folder.exists():
        game_folder.mkdir()

    game_folder = game_folder / Path(game_name)

    if game_folder.exists():
        return {"status": "error", "message": f"Hra {game_name} již existuje"}
    game_folder.mkdir()
    return {"status": "ok"}


def validate_game_folder(game_name: Path, page_name: str, check_page_exists: bool) -> tuple[bool, str, Path | None]:
    game_folder_path = Path(current_app.config.get("GAMES_FOLDER_LIVE"))
    if check_page_exists and not game_folder_path or not game_folder_path.exists():
        return False, "Neexistuje složka s hrami", None

    game_folder = game_folder_path / game_name
    if not game_folder.exists():
        game_folder.mkdir()

    page_path = game_folder / f"{page_name}.html"
    if check_page_exists and not page_path.exists():
        return False, f"Stránka '{page_name}' neexistuje", None

    return True, "", page_path

@socketio.on("page_html_set")
def handle_page_html_set(json: dict) -> dict:
    game_name = json.get("game_name")
    game_page = json.get("game_page")
    page_content = json.get("game_content")

    if not page_content:
        return {"status": "error", "message": "Obsah stránky nesmí být prázdný"}

    is_valid, message, path = validate_game_folder(game_name, game_page, check_page_exists=False)
    if not is_valid:
        return {"status": "error", "message": message}
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(page_content)
            return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": f"Chyba zápisu do souboru: {e}"}


@socketio.on("page_html_get")
def handle_page_html_get(json: dict) -> dict:
    game_name = json.get("game_name")
    game_page = json.get("game_page")

    is_valid, message, path = validate_game_folder(game_name, game_page, check_page_exists=True)
    if not is_valid:
        return {"status": "error", "message": message}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {"status": "ok", "content": f.read()}
    except Exception as e:
        return {"status": "error", "message": f"Chyba čtení souboru: {e}"}