import json
import os
from engineio.async_drivers import eventlet
from nanoid import generate
from enum import Enum

class DatabaseException(Exception):
    pass

class DatabaseKeys(Enum):
    VAR = "VAR_"
    ARR = "ARR_"

    def __add__(self, other):
        return self.value + str(other)

def save_data(func):
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        # self.save_to_file()
        return result
    return wrapper


class Database:
    def __init__(self):
        self.directory = None
        self.file = None
        self.path_to_data = None
        self.data = {}

    def init(self, directory: str, file_name: str, clear_data: bool = False):
        if not directory or not os.path.exists(directory):
            raise DatabaseException('Cesta není poskytnuta nebo neexistuje - Database.init()')
        if not file_name or not file_name.endswith('.json'):
            raise DatabaseException('Soubor nebyl poskytnut nebo není JSON soubor - Database.init()')

        self.directory = directory
        self.file = file_name
        self.path_to_data = os.path.join(directory, file_name)
        if clear_data:
            self.clear_data()
        self.load_data()

    def save_to_file(self):
        with open(self.path_to_data, 'w') as f:
            json.dump(self.data, f, indent=4)

    def load_data(self, optional_path: str = None):
        path_to_data = optional_path or self.path_to_data

        if not os.path.exists(path_to_data):
            self.save_to_file()
        with open(self.path_to_data, 'r') as f:
            try:
                self.data = json.load(f)
            except json.JSONDecodeError:
                self.data = {}
                self.save_to_file()

    def clear_data(self):
        self.data = {}
        self.save_to_file()


    def get_all_data(self):
        return self.data

    def set_data(self, data: dict):
        self.data = data
        self.save_to_file()

    def save_data_periodically(self):
        eventlet.sleep(1)
        while True:
            self.save_to_file()
            print("Data saved to file")
            eventlet.sleep(5)

    ##########################################
    def edit_mode_is_on(self):
        return self.var_key_get('global', 'edit_mode', False)

    def set_edit_mode(self, value: bool):
        self.var_key_set('global', 'edit_mode', value)

    ##########################################

    def var_key_get(self, project: str, key: str, default_value=None):
        key = DatabaseKeys.VAR + key
        if project not in self.data:
            return default_value
        return self.data[project].get(key, default_value)

    def var_key_set(self, project: str, key: str, value):
        key = DatabaseKeys.VAR + key
        if project not in self.data:
            self.data[project] = {}
        self.data[project][key] = value

    def var_key_delete(self, project: str, key: str):
        key = DatabaseKeys.VAR + key
        if project in self.data and key in self.data[project]:
            del self.data[project][key]
            return True
        return False

    def var_key_exists(self, project: str, key: str):
        key = DatabaseKeys.VAR + key
        return project in self.data and key in self.data[project]

    ##########################################

    # add record
    def array_add_record(self, project: str, array_name: str, value):
        array_name = DatabaseKeys.ARR + array_name
        if project not in self.data:
            self.data[project] = {}
        if array_name not in self.data[project]:
            self.data[project][array_name] = {}
        self.data[project][array_name][generate(size=10)] = value

    def _record_exists(self, project_prefix: str, array_name: str, record_id: str) -> bool:
        return project_prefix in self.data and array_name in self.data[project_prefix] and record_id in self.data[project_prefix][array_name]

    # remove record
    def array_remove_record(self, project: str, array_name: str, record_id: str):
        array_name = DatabaseKeys.ARR + array_name
        if self._record_exists(project, array_name, record_id):
            del self.data[project][array_name][record_id]
            return True
        return False

    # update record
    def array_update_record(self, project: str, array_name: str, record_id: str, value):
        array_name = DatabaseKeys.ARR + array_name
        if self._record_exists(project, array_name, record_id):
            self.data[project][array_name][record_id] = value
            return True
        return False

    def array_get_all_records(self, project: str, array_name: str):
        array_name = DatabaseKeys.ARR + array_name
        return self.data[project].get(array_name, {}) if project in self.data else {}


    def array_clear_records(self, project: str, array_name: str):
        array_name = DatabaseKeys.ARR + array_name
        if project in self.data and array_name in self.data[project]:
            del self.data[project][array_name]
            return True
        return False


    def array_list_projects(self):
        return list(self.data.keys())
