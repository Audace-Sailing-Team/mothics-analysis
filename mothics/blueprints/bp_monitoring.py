import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request, Response, current_app, abort, send_file
from bokeh.embed import server_document
from ..helpers import compute_status, get_tile_zoom_levels
from ..track import Track


monitor_bp = Blueprint('monitor', __name__)
# GPS keys cache
GPS_KEYS_CACHE = {}


@monitor_bp.route("/")
def index():
    return render_template("index.html", online=current_app.config["ONLINE_MODE"])


@monitor_bp.route("/api/track_list")
def track_list():
    db = current_app.config['TRACK_MANAGER']
    return jsonify([
        {"filename": t["filename"], "label": t.get("track_datetime") or t["filename"]}
        for t in db.tracks
    ])

@monitor_bp.route("/api/load_track/<filename>")
def load_track_with_timestamps(filename):
    db = current_app.config['TRACK_MANAGER']
    path = db.get_track_path(filename)
    if not path or not path.exists():
        return jsonify({"error": "Track not found"}), 404

    analysis_track = Track()
    analysis_track.load(path.as_posix())
    analysis_track.mode = "replay"
    analysis_track._replay_index = 0
    current_app.config['ANALYSIS_TRACK'] = analysis_track

    timestamps = [
        dp.timestamp.isoformat() if hasattr(dp.timestamp, 'isoformat') else str(dp.timestamp)
        for dp in analysis_track.data_points
    ]

    return jsonify({
        "status": "ok",
        "total_points": len(analysis_track.data_points),
        "timestamps": timestamps
    })


@monitor_bp.route('/tiles/<int:z>/<int:x>/<int:y>.png')
def serve_tile(z, x, y):
    path = os.path.join(current_app.root_path, 'static', 'tiles', str(z), str(x), f"{y}.png")
    if os.path.exists(path):
        return send_file(path)
    else:
        abort(404)


@monitor_bp.route("/api/gps_info")
def gps_info():
    track = current_app.config.get('ANALYSIS_TRACK')
    if track:
        latest = track.get_current().data_points[-1].to_dict()
    else:
        db = current_app.config['TRACK_MANAGER']
        # TODO: fallback dp is not gonna work
        latest = db.data_points[-1].to_dict() if db.data_points else {}

    lat_key = next((k for k in latest if k.endswith("/gps/lat")), None)
    lon_key = next((k for k in latest if k.endswith("/gps/long")), None)
    spd_key = next((k for k in latest if "/gps/speed" in k), None)

    lat = latest.get(lat_key)
    lon = latest.get(lon_key)
    speed = latest.get(spd_key) if spd_key else None

    status_key = next((k for k in latest if k.endswith("/gps/status")), None)
    gps_available = latest.get(status_key, False)

    tile_dir = current_app.config['GPS_TILES_DIRECTORY']
    track_variable = current_app.config.get('TRACK_VARIABLE', 'speed')
    track_thresholds = current_app.config.get('TRACK_THRESHOLDS', [1, 5, 15])
    track_colors = current_app.config.get('TRACK_COLORS', ["#3366cc", "#66cc66", "#ffcc00", "#cc3333"])
    track_units = current_app.config.get('TRACK_UNITS', None)
    min_zoom, max_zoom = get_tile_zoom_levels(tile_dir=tile_dir)

    return jsonify({
        "gps_available": gps_available,
        "latest_position": {
            "lat": lat,
            "lon": lon,
            "speed": speed
        } if gps_available else None,
        "zoom": {
            "min": min_zoom,
            "max": max_zoom
        },
        "track_coloring": {
            "key": track_variable,
            "thresholds": track_thresholds,
            "colors": track_colors,
            "units": track_units
        }
    })

@monitor_bp.route("/api/scrub_window")
def scrub_window():
    track = current_app.config['ANALYSIS_TRACK']
    if not track:
        return jsonify({"error": "No track loaded"}), 400

    try:
        start_str = request.args.get("start", "").replace("Z", "")
        end_str = request.args.get("end", "").replace("Z", "")
        start_ts = datetime.fromisoformat(start_str)
        end_ts = datetime.fromisoformat(end_str)
    except Exception as e:
        return jsonify({"error": f"Invalid timestamp: {e}"}), 400

    current_app.config["SCRUB_WINDOW"] = (start_ts, end_ts)
    return jsonify({"status": "ok"})


@monitor_bp.route("/api/gps_track")
def gps_track():
    db = current_app.config['TRACK_MANAGER']
    window_minutes = current_app.config.get("GPS_HISTORY_MINUTES", 10)
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)

    # Filter all data points newer than the cutoff timestamp
    datapoints = [
        dp for dp in db.data_points
        if "timestamp" in dp.to_dict() and
        datetime.fromisoformat(dp.to_dict()["timestamp"]) >= cutoff
    ]
    
    track_data = []

    track_key = current_app.config.get("TRACK_VARIABLE", "speed")
    for dp in datapoints:
        d = dp.to_dict()

        lat_key = next((k for k in d if k.endswith("/gps/lat")), None)
        lon_key = next((k for k in d if k.endswith("/gps/long")), None)
        value_key = next((k for k in d if track_key in k and "/gps/" in k), None)

        if lat_key and lon_key:
            lat = d[lat_key]
            lon = d[lon_key]
            val = d.get(value_key)

            track_data.append({
                "lat": lat,
                "lon": lon,
                "value": val,
                "timestamp": d.get("timestamp")
            })

    return jsonify({"track": track_data})


@monitor_bp.route("/api/gps_track_window")
def gps_track_window():
    track = current_app.config.get("ANALYSIS_TRACK")
    if not track:
        return jsonify({"track": []})

    # window & stride
    start = datetime.fromisoformat(request.args["start"])
    end   = datetime.fromisoformat(request.args["end"])
    stride = max(int(request.args.get("stride", 1)), 1)

    # ─── variable for colouring ───────────────────────────────────────
    color_var = request.args.get("color_var") or current_app.config.get(
        "TRACK_VARIABLE", "speed"
    )

    thresholds = current_app.config.get("TRACK_THRESHOLDS", [1, 5, 15])
    colours    = current_app.config.get("TRACK_COLORS",
                                        ["#3366cc", "#66cc66", "#ffcc00", "#cc3333"])
    units      = current_app.config.get("TRACK_UNITS", "")

    rows, lat_key, lon_key, val_key = [], None, None, None
    for i, dp in enumerate(track.data_points):
        if i % stride or not (start <= dp.timestamp <= end):
            continue

        # ── discover or reuse GPS keys ───────────────────────────────────
        fname = current_app.config.get("CURRENT_TRACK_FILE")
        if fname in GPS_KEYS_CACHE:
            lat_key, lon_key = GPS_KEYS_CACHE[fname]
        else:
            sample_dp = next((dp for dp in track.data_points if dp.input_data), None)
            if not sample_dp:
                raise ValueError("track has no datapoints")
            lat_key = next(k for k in sample_dp.input_data if k.endswith("/gps/lat"))
            lon_key = next(k for k in sample_dp.input_data if k.endswith("/gps/long"))
            GPS_KEYS_CACHE[fname] = (lat_key, lon_key)
        
        # if lat_key is None:     # discover once
        #     lat_key = next((k for k in dp.input_data if k.endswith("/gps/lat")), None)
        #     lon_key = next((k for k in dp.input_data if k.endswith("/gps/long")), None)
        #     val_key = next((k for k in dp.input_data if color_var in k), None)

        lat, lon = dp.input_data.get(lat_key), dp.input_data.get(lon_key)
        val      = dp.input_data.get(val_key) if val_key else None
        if lat is not None and lon is not None:
            rows.append({"lat": lat, "lon": lon, "val": val})

    return jsonify({"track": rows,
                    "thresholds": thresholds,
                    "colours": colours,
                    "units": units,
                    "color_var": color_var})


@monitor_bp.route("/api/track_plot_data")
def track_plot_data():
    track = current_app.config.get("ANALYSIS_TRACK")
    hidden = current_app.config.get("HIDDEN_DATA_PLOTS", [])
    if not track:
        return jsonify({"error": "No track loaded"}), 400

    try:
        start_str = request.args.get("start", "").replace("Z", "")
        end_str   = request.args.get("end", "").replace("Z", "")
        start_ts  = datetime.fromisoformat(start_str)
        end_ts    = datetime.fromisoformat(end_str)
    except Exception as e:
        return jsonify({"error": f"Invalid timestamp: {e}"}), 400

    # Optional variable filter
    var_filter = request.args.get("vars", "")
    filter_set = set(var_filter.split(",")) if var_filter else None

    # Filter points
    points = [dp for dp in track.data_points if start_ts <= dp.timestamp <= end_ts]
    if not points:
        return jsonify({"timestamps": [], "vars": {}})

    timestamps = [dp.timestamp.isoformat() for dp in points]
    vars_by_name = {}

    thesaurus = current_app.config.get("DATA_THESAURUS", {})
    
    for dp in points:
        for key, val in dp.input_data.items():
            if not filter_set or key in filter_set:
                try:
                    val = float(val)
                    vars_by_name.setdefault(key, []).append(val)
                except (ValueError, TypeError):
                    continue
    
    return jsonify({
        "timestamps": timestamps,
        "vars": {
            k: v for k, v in vars_by_name.items() if k not in hidden
        },
        "aliases": {k: thesaurus.get(k, k) for k in vars_by_name}
    })
