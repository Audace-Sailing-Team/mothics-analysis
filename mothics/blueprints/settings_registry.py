"""
All of the settings shown in the WebApp (`bp_settings.py`) are
defined and configured here in a centralized registry.

Structure
---------
The registry is a dictionary, where each key is the name of a setting
and each value is a dictionary containing metadata and logic for how
to handle that setting in the UI and backend.

Example entry:

    "setting_name": {
        "type": "float",
        "tab": "Webapp",
        "label": "User-friendly label for the field",
        "placeholder": "Optional hint text",
        "validate": lambda v: v > 0,
        "choices": ["option1", "option2"],
        "setter_name": "some_runtime_setter",
        "config_path": ("section", "subkey"),
        "log_success": "Setting updated to {value}."
    }

Field descriptions:

 - `type`: type expected from user input; one of "string", "float", "int", "bool"
 - `tab`: tab name shown in the UI where the field will appear
 - `label`: human-readable label shown above the form input
 - `placeholder`: optional string shown as a hint inside the input box
 - `validate`: optional validation function applied after parsing
 - `choices`: optional list of values for select dropdown inputs
 - `setter_name`: name of a callable in `current_app.config['SETTERS']` for real-time updates
 - `real_time_setter`: alternatively, a direct function `(value, system_manager) -> None` for complex updates
 - `config_path`: tuple describing where the value lives in the nested config
 - `log_success`: log or UI message on successful update, with `{value}` placeholder

Notes
-----
- Either `setter_name` or `real_time_setter` must be provided.
- If `choices` is present, the form renders a `<select>` instead of a text input.
- If a setting is missing any optional field, sensible defaults will be used in the UI.

"""
SETTINGS_REGISTRY = {
    # ========= Database =========
    "database_validation": {
        "type": "bool",
        "tab": "Database",
        "label": "Enable track schema validation",
        "validate": lambda v: isinstance(v, bool),
        "setter_name": "set_database_validation",
        "config_path": ("database", "validation"),
        "log_success": "Track validation set to {value}"
    },
    "database_startup": {
        "type": "bool",
        "tab": "Database",
        "label": "Start database at launch",
        "validate": lambda v: isinstance(v, bool),
        "setter_name": "set_database_startup",
        "config_path": ("database", "startup"),
        "log_success": "Database startup set to {value}"
    },

    # ========= File Output =========
    "output_dir": {
        "type": "string",
        "tab": "Files",
        "label": "Data output directory",
        "placeholder": "e.g. data/",
        "setter_name": "set_output_dir",
        "config_path": ("files", "output_dir"),
        "log_success": "Output directory set to {value}"
    },
    "tile_dir": {
        "type": "string",
        "tab": "Files",
        "label": "Tile cache directory",
        "placeholder": "e.g. mothics/static/tiles",
        "setter_name": "set_tile_dir",
        "config_path": ("files", "tile_dir"),
        "log_success": "Tile directory set to {value}"
    },
    "logger_fname": {
        "type": "string",
        "tab": "Files",
        "label": "Log file name",
        "placeholder": "e.g. default.log",
        "setter_name": "set_logger_fname",
        "config_path": ("files", "logger_fname"),
        "log_success": "Logger file name set to {value}"
    },
    # ========= Webapp (advanced) =========
    "data_thesaurus": {
        "type": "kvtable",
        "tab": "Webapp",
        "label": "Sensor values aliases",
        "setter_name": "set_data_thesaurus",
        "config_path": ("webapp", "data_thesaurus"),
        "log_success": "Data thesaurus updated."
    },
    "hidden_data_plots": {
        "type": "taglist",
        "tab": "Webapp",
        "label": "Hidden sensor values",
        "setter_name": "set_hidden_data",
        "config_path": ("webapp", "hidden_data_plots"),
        "validate": lambda raw: True,
        "log_success": "Hidden-data list updated."
    },
    "webapp_port": {
        "type": "int",
        "tab": "Webapp",
        "label": "WebApp port",
        "placeholder": "e.g. 5050",
        "validate": lambda v: 1024 <= v <= 65535,
        "setter_name": "set_webapp_port",
        "config_path": ("webapp", "port"),
        "log_success": "WebApp port set to {value} (restart required)"
    }
}


