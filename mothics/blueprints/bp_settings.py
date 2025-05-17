import json
from flask import Blueprint, render_template, jsonify, request, Response, current_app

from ..helpers import tipify, write_config, list_required_tiles, download_tiles
from .settings_registry import SETTINGS_REGISTRY

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/estimate_tiles")
def estimate_tiles():
    bbox = request.args.get("bbox", "")
    zooms = request.args.get("zooms", "")

    try:
        lat_min, lon_min, lat_max, lon_max = map(float, bbox.split(","))
        zoom_levels = list(map(int, zooms.split(",")))
        tiles = list_required_tiles((lat_min, lat_max), (lon_min, lon_max), zoom_levels)
        count = len(tiles)
        size_mb = count * 20 / 1024  # 20 kB per tile, rough average
        return jsonify({"count": count, "size_mb": round(size_mb, 1)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    
@settings_bp.route("/api/download_tiles", methods=["POST"])
def download_tiles_api():
    bbox = request.args.get("bbox", "")
    zooms = request.args.get("zooms", "")
    try:
        bb = tuple(map(float, bbox.split(",")))
        zs = list(map(int, zooms.split(",")))
        tile_dir = current_app.config["CONFIG_DATA"]["files"]["tile_dir"]
        bb_lat = [bb[0], bb[2]]
        bb_lon = [bb[1], bb[3]]
        saved = download_tiles(bb_lat, bb_lon, zs, output_dir=tile_dir)
        return jsonify({"saved": saved})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/write_config", methods=["POST"])
def write_config_api():
    cfg = current_app.config.get("CONFIG_DATA")
    try:
        write_config(cfg, "config.toml")
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    
@settings_bp.route("/settings", methods=["GET", "POST"])
def settings():
    success_message = None
    error_message = None

    cfg_data = current_app.config["CONFIG_DATA"]
    current_vals = {
        k: lookup_config_value(field["config_path"], cfg_data)
        for k, field in SETTINGS_REGISTRY.items()
    }

    if request.method == "POST":
        for field, raw_value in request.form.items():
            if field not in SETTINGS_REGISTRY:
                continue  # Skip unknown fields

            spec = SETTINGS_REGISTRY[field]
            try:
                value = parse_value(raw_value, spec["type"])
                
                if "validate" in spec and not spec["validate"](value):
                    raise ValueError(f"Validation failed for {field} = {value}")

                apply_runtime_setter(spec, value)

                success_message = spec.get("log_success", f"Updated {field} to {value}").format(value=value)

            except Exception as e:
                error_message = f"Error processing {field}: {e}"

    # POST logic completed
    cfg_data = current_app.config["CONFIG_DATA"]  # ← now contains updated values
    current_vals = {
        k: lookup_config_value(field["config_path"], cfg_data)
        for k, field in SETTINGS_REGISTRY.items()
    }
    return render_template("settings.html",
                           success=success_message,
                           error=error_message,
                           registry=SETTINGS_REGISTRY,
                           current=current_vals,
                           online=current_app.config["ONLINE_MODE"])


def parse_value(raw, typ):
    if typ == "int":
        return int(raw)
    if typ == "float":
        return float(raw)
    if typ == "bool":
        return raw.lower() in ["true", "1", "yes"]
    if typ == "taglist":
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError("Expected list for taglist")
            return parsed
        except json.JSONDecodeError:
            # fallback: try CSV
            return [x.strip() for x in raw.split(",") if x.strip()]
    if typ == "kvtable":
        if isinstance(raw, dict):
            return raw  # already parsed
        try:
            return json.loads(raw)
        except Exception:
            raise ValueError("Invalid JSON for kvtable")
    if typ == "text":
        return str(raw)  # multiline textarea, no parsing
    return str(raw)  # fallback


def apply_runtime_setter(spec, value):
    if "setter_name" in spec:
        name = spec["setter_name"]
        action = current_app.config.get("SETTINGS_ACTIONS", {}).get(name)
        if not action:
            raise RuntimeError(f"No action registered for '{name}'")
        return action(value, current_app)
    raise RuntimeError("No setter_name defined in settings spec.")


def lookup_config_value(path, cfg):
    ref = cfg
    for key in path:
        ref = ref.get(key, {})
    return ref if ref != {} else ""
