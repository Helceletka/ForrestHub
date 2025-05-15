\
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app
from app.init import db, socketio
from app.games import copy_default_game
# It's generally better to manage shared state (like game_status, connected_clients)
# via a dedicated service or app context extensions rather than direct module import,
# but for now, this directly accesses them from socketio_events.
from app import socketio_events

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Helper functions for game folder validation and path creation/checking
# These are specific to the needs of page_html_set and page_html_get.

def _ensure_base_games_folder_exists():
    game_folder_path_config = current_app.config.get("GAMES_FOLDER_LIVE")
    if not game_folder_path_config:
        return False, "Konfigurace GAMES_FOLDER_LIVE chybí", None

    game_folder_base = Path(game_folder_path_config)
    if not game_folder_base.exists():
        try:
            game_folder_base.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, f"Nepodařilo se vytvořit kořenovou složku her (GAMES_FOLDER_LIVE): {e}", None
    return True, "", game_folder_base

def _validate_and_get_page_path_for_set(game_name_str: str, page_name_str: str) -> tuple[bool, str, Path | None]:
    success, msg, game_folder_base = _ensure_base_games_folder_exists()
    if not success:
        return False, msg, None

    game_folder = game_folder_base / Path(game_name_str)
    if not game_folder.exists():
        try:
            game_folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, f"Nepodařilo se vytvořit složku hry '{game_name_str}': {e}", None

    page_path = game_folder / f"{page_name_str}.html"
    return True, "", page_path

def _validate_and_get_page_path_for_get(game_name_str: str, page_name_str: str) -> tuple[bool, str, Path | None]:
    game_folder_path_config = current_app.config.get("GAMES_FOLDER_LIVE")
    if not game_folder_path_config:
        return False, "Konfigurace GAMES_FOLDER_LIVE chybí", None

    game_folder_base = Path(game_folder_path_config)
    if not game_folder_base.exists():
        return False, "Neexistuje kořenová složka s hrami (GAMES_FOLDER_LIVE)", None

    game_folder = game_folder_base / Path(game_name_str)
    if not game_folder.exists():
        return False, f"Složka hry '{game_name_str}' neexistuje", None

    page_path = game_folder / f"{page_name_str}.html"
    if not page_path.exists():
        return False, f"Stránka '{page_name_str}.html' ve hře '{game_name_str}' neexistuje", None

    return True, "", page_path


@api_bp.route("/", methods=["GET"])
def api_index():
    return jsonify({"status": "ok", "message": "API is running"})


# Admin Config
@api_bp.route("/admin/message", methods=["POST"])
def admin_send_message():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"status": "error", "message": "Message is required"}), 400
    message = data.get("message")
    socketio.emit("admin_messages", message, broadcast=True)
    return jsonify({"status": "success", "message_sent": message})

@api_bp.route("/clients/count", methods=["GET"])
def get_clients_count():
    return jsonify({"status": "ok", "count": socketio_events.connected_clients})

@api_bp.route("/game/status", methods=["GET"])
def game_status_get_http():
    return jsonify({"status": "ok", "game_status": socketio_events.game_status})

@api_bp.route("/game/status", methods=["POST"])
def game_status_set_http():
    data = request.get_json()
    if not data or "status" not in data:
        return jsonify({"status": "error", "message": "Status is required"}), 400
    new_status = data.get("status")
    socketio_events.game_status = new_status
    socketio.emit("game_status", new_status, broadcast=True)
    return jsonify({"status": "success", "game_status": new_status})

# Edit Mode
@api_bp.route("/edit_mode", methods=["GET"])
def edit_mode_get_http():
    return jsonify({"status": "ok", "edit_mode": db.edit_mode_is_on()})

@api_bp.route("/edit_mode", methods=["POST"])
def edit_mode_set_http():
    data = request.get_json()
    if not data or "edit_mode_on" not in data or not isinstance(data.get("edit_mode_on"), bool):
        return jsonify({"status": "error", "message": "edit_mode_on (boolean) is required"}), 400

    edit_mode_on = data.get("edit_mode_on")
    db.set_edit_mode(edit_mode_on)
    socketio.emit("edit_mode", edit_mode_on, broadcast=True)

    copy_result_msg = None
    if edit_mode_on:
        copy_result = copy_default_game() # Assuming this returns a status or message
        copy_result_msg = str(copy_result) if copy_result else "Default game copied (or no action taken)."

    return jsonify({"status": "success", "edit_mode": edit_mode_on, "copy_default_game_status": copy_result_msg})

# Admin Access
@api_bp.route("/db/all_data", methods=["GET"])
def db_get_all_data_http():
    return jsonify({"status": "ok", "data": db.get_all_data()})

@api_bp.route("/db/delete_all_data", methods=["POST"]) # Using POST for action, could be DELETE
def db_delete_all_data_http():
    db.clear_data()
    # Consider emitting an event if other parts of the application need to react to data clear
    # socketio.emit("database_cleared", broadcast=True)
    return jsonify({"status": "ok", "message": "All data cleared."})

# VAR
@api_bp.route("/var", methods=["POST"]) # Corresponds to var_key_set
def var_key_set_http():
    data = request.get_json()
    if not data: return jsonify({"status": "error", "message": "JSON payload required"}), 400
    project = data.get("project")
    key = data.get("key")
    value = data.get("value")
    if project is None or key is None:
        return jsonify({"status": "error", "message": "Project and key are required"}), 400

    # Replicating the exact db call from the socketio handler handle_key_set
    db.var_key_set(project, key, value)
    result_data = db.var_key_get(project, key, value)
    return jsonify({"status": "ok", "data": result_data})

@api_bp.route("/var/exists", methods=["GET"])
def var_key_exist_http():
    project = request.args.get("project")
    key = request.args.get("key")
    if not project or not key:
        return jsonify({"status": "error", "message": "Project and key query parameters are required"}), 400
    return jsonify({"status": "ok", "exists": db.var_key_exists(project, key)})

@api_bp.route("/var", methods=["GET"]) # Corresponds to var_key_get
def var_key_get_http():
    project = request.args.get("project")
    key = request.args.get("key")
    default_value = request.args.get("defaultValue", "")
    if not project or not key:
        return jsonify({"status": "error", "message": "Project and key query parameters are required"}), 400
    return jsonify({"status": "ok", "data": db.var_key_get(project, key, default_value)})

@api_bp.route("/var", methods=["DELETE"])
def var_key_delete_http():
    project = request.args.get("project")
    key = request.args.get("key")
    if not project or not key: # Allow project/key in body for DELETE too if preferred
        data = request.get_json(silent=True)
        if data:
            project = project or data.get("project")
            key = key or data.get("key")
    if not project or not key:
        return jsonify({"status": "error", "message": "Project and key (in query or JSON body) are required"}), 400

    deleted_data = db.var_key_delete(project, key)
    return jsonify({"status": "ok", "data": deleted_data})

# Array
@api_bp.route("/array/record", methods=["POST"])
def array_add_record_http():
    data = request.get_json()
    if not data: return jsonify({"status": "error", "message": "JSON payload required"}), 400
    project = data.get("project")
    array_name = data.get("arrayName")
    value = data.get("value")
    record_id = data.get("recordId")
    if project is None or array_name is None or value is None:
        return jsonify({"status": "error", "message": "Project, arrayName, and value are required"}), 400
    return jsonify({"status": "ok", "data": db.array_add_record(project, array_name, value, record_id)})

@api_bp.route("/array/record", methods=["DELETE"])
def array_remove_record_http():
    project = request.args.get("project")
    array_name = request.args.get("arrayName")
    record_id = request.args.get("recordId")
    if not project or not array_name or not record_id: # Allow in body too
        data = request.get_json(silent=True)
        if data:
            project = project or data.get("project")
            array_name = array_name or data.get("arrayName")
            record_id = record_id or data.get("recordId")
    if not project or not array_name or not record_id:
        return jsonify({"status": "error", "message": "Project, arrayName, and recordId (in query or JSON body) are required"}), 400
    return jsonify({"status": "ok", "data": db.array_remove_record(project, array_name, record_id)})

@api_bp.route("/array/record", methods=["GET"])
def array_get_record_http():
    project = request.args.get("project")
    array_name = request.args.get("arrayName")
    record_id = request.args.get("recordId")
    if not project or not array_name or not record_id:
        return jsonify({"status": "error", "message": "Project, arrayName, and recordId query parameters are required"}), 400
    return jsonify({"status": "ok", "data": db.array_get_record(project, array_name, record_id)})

@api_bp.route("/array/record", methods=["PUT"])
def array_update_record_http():
    data = request.get_json()
    if not data: return jsonify({"status": "error", "message": "JSON payload required"}), 400
    project = data.get("project")
    array_name = data.get("arrayName")
    record_id = data.get("recordId")
    value = data.get("value")
    if project is None or array_name is None or record_id is None or value is None:
        return jsonify({"status": "error", "message": "Project, arrayName, recordId, and value are required"}), 400
    return jsonify({"status": "ok", "data": db.array_update_record(project, array_name, record_id, value)})

@api_bp.route("/array/all_records", methods=["GET"])
def array_get_all_records_http():
    project = request.args.get("project")
    array_name = request.args.get("arrayName")
    if not project or not array_name:
        return jsonify({"status": "error", "message": "Project and arrayName query parameters are required"}), 400
    return jsonify({"status": "ok", "data": db.array_get_all_records(project, array_name)})

@api_bp.route("/array/record/exists", methods=["GET"])
def array_record_exists_http():
    project = request.args.get("project")
    array_name = request.args.get("arrayName")
    record_id = request.args.get("recordId")
    if not project or not array_name or not record_id:
        return jsonify({"status": "error", "message": "Project, arrayName, and recordId query parameters are required"}), 400
    return jsonify({"status": "ok", "exists": db.array_record_exists(project, array_name, record_id)})

@api_bp.route("/array/clear_records", methods=["POST"])
def array_clear_records_http():
    data = request.get_json()
    if not data: return jsonify({"status": "error", "message": "JSON payload required"}), 400
    project = data.get("project")
    array_name = data.get("arrayName")
    if project is None or array_name is None:
        return jsonify({"status": "error", "message": "Project and arrayName are required"}), 400
    db.array_clear_records(project, array_name)
    return jsonify({"status": "ok", "message": f"Records cleared for project '{project}', array '{array_name}'."})

@api_bp.route("/array/projects", methods=["GET"])
def array_list_projects_http():
    return jsonify({"status": "ok", "data": db.array_list_projects()})

# Edit Game
@api_bp.route("/game/new", methods=["POST"])
def add_new_game_http():
    data = request.get_json()
    if not data or "game_name" not in data:
        return jsonify({"status": "error", "message": "game_name is required"}), 400
    game_name = data.get("game_name")

    success, msg, game_folder_base = _ensure_base_games_folder_exists()
    if not success:
        return jsonify({"status": "error", "message": msg}), 500

    game_folder = game_folder_base / Path(game_name)
    if game_folder.exists():
        return jsonify({"status": "error", "message": f"Hra {game_name} již existuje"}), 409
    try:
        game_folder.mkdir()
        return jsonify({"status": "ok", "message": f"Hra {game_name} vytvořena."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Nepodařilo se vytvořit složku hry {game_name}: {e}"}), 500

@api_bp.route("/game/page_html", methods=["POST"])
def page_html_set_http():
    data = request.get_json()
    if not data: return jsonify({"status": "error", "message": "JSON payload required"}), 400
    game_name = data.get("game_name")
    game_page = data.get("game_page") # This is page name without .html
    page_content = data.get("game_content")

    if not game_name or not game_page:
        return jsonify({"status": "error", "message": "game_name and game_page are required"}), 400
    if page_content is None:
        return jsonify({"status": "error", "message": "game_content is required (can be empty string)"}), 400

    is_valid, message, path = _validate_and_get_page_path_for_set(game_name, game_page)
    if not is_valid:
        return jsonify({"status": "error", "message": message}), 500

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(page_content)
        # socketio.emit('page_updated', {'game_name': game_name, 'game_page': game_page}, broadcast=True)
        return jsonify({"status": "ok", "message": f"Page '{game_page}.html' in game '{game_name}' saved."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba zápisu do souboru: {e}"}), 500

@api_bp.route("/game/page_html", methods=["GET"])
def page_html_get_http():
    game_name = request.args.get("game_name")
    game_page = request.args.get("game_page")

    if not game_name or not game_page:
        return jsonify({"status": "error", "message": "game_name and game_page query parameters are required"}), 400

    is_valid, message, path = _validate_and_get_page_path_for_get(game_name, game_page)
    if not is_valid:
        status_code = 404 if "neexistuje" in message.lower() else 500
        return jsonify({"status": "error", "message": message}), status_code

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"status": "ok", "content": content})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba čtení souboru: {e}"}), 500
