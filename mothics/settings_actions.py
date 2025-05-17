import json
from functools import wraps

def mirror_to_config(path):
    """
    Decorator factory.
    `path` is the tuple from SETTINGS_REGISTRY ("files", "output_dir", ...).
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(value, app):
            # 1. Run the live effect
            result = fn(value, app)

            # 2. Persist into CONFIG_DATA in memory
            conf = app.config["CONFIG_DATA"]
            for key in path[:-1]:
                conf = conf.setdefault(key, {})
            conf[path[-1]] = value

            return result
        return wrapper
    return decorator


@mirror_to_config(("files", "output_dir"))
def set_output_dir(value, app):
    app.config["OUTPUT_DIR"] = value            # live effect

@mirror_to_config(("files", "tile_dir"))
def set_tile_dir(value, app):
    app.config["TILE_DIR"] = value

@mirror_to_config(("files", "logger_fname"))
def set_logger_fname(value, app):
    app.config["LOGGER_FNAME"] = value
    # if you want, you could also swap log handlers here

@mirror_to_config(("database", "validation"))
def set_database_validation(value, app):
    app.config["DB_VALIDATE"] = value           # or call db.toggle_validation()

@mirror_to_config(("database", "startup"))
def set_database_startup(value, app):
    app.config["DB_STARTUP"] = value

@mirror_to_config(("webapp", "data_thesaurus"))
def set_data_thesaurus(text_value, app):
    mapping = text_value
    app.config["DATA_THESAURUS"] = mapping
    # Live effect: any components that cache aliases should refresh
    # e.g. reload variable selectors:
    # broadcast_event("refresh_variable_labels", mapping)

@mirror_to_config(("webapp", "hidden_data_plots"))
def set_hidden_data(text_value, app):
    hidden = parse_list_textarea(text_value)
    app.config["HIDDEN_DATA_PLOTS"] = hidden

@mirror_to_config(("webapp", "port"))
def set_webapp_port(value, app):
    app.config["WEBAPP_PORT"] = value  # in-memory reference
    # NOTE: Will only take effect next time app starts
    
ACTIONS = {
    "set_output_dir": set_output_dir,
    "set_tile_dir": set_tile_dir,
    "set_logger_fname": set_logger_fname,
    "set_database_validation": set_database_validation,
    "set_database_startup": set_database_startup,
    "set_data_thesaurus": set_data_thesaurus,
    "set_hidden_data": set_hidden_data,
    "set_webapp_port": set_webapp_port
}


def parse_kv_textarea(txt: str) -> dict:
    """
    "rm1/imu/roll = Heel angle\nrm2/gps/speed = Boat speed" → dict
    Ignores empty lines & comments (# …)
    """
    mapping = {}
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Missing '=' in line: {line}")
        k, v = [p.strip() for p in line.split("=", 1)]
        mapping[k] = v
    return mapping


def parse_list_textarea(txt):
    if isinstance(txt, list):  # Already parsed (e.g. from Tagify)
        return txt
    return [line.strip() for line in txt.splitlines() if line.strip() and not line.strip().startswith("#")]
