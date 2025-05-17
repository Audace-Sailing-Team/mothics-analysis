import secrets
import socket
import os
import requests
import time
import logging
from flask import Flask
from threading import Thread
from flask_compress import Compress
from tornado.log import access_log, app_log, gen_log
from waitress import serve
from pprint import pprint

from .blueprints.bp_monitoring import monitor_bp
from .blueprints.bp_logging import log_bp
from .blueprints.bp_saving import save_bp
from .blueprints.bp_settings import settings_bp
from .blueprints.bp_database import database_bp
from .settings_actions import ACTIONS
from .helpers import check_internet_connectivity


class WebApp:
    def __init__(self, logger_fname=None, rm_thesaurus=None,
                 data_thesaurus=None, hidden_data_plots=None,
                 track_manager=None, track_manager_directory=None,
                 gps_tiles_directory=None, out_dir=None,
                 instance_dir=None, config_dict=None):
        self.logger_fname = logger_fname
        """Logger filename"""
        self.rm_thesaurus = rm_thesaurus
        """Aliases for remote unit names"""
        self.data_thesaurus = data_thesaurus
        """Aliases for sensor data names"""
        self.hidden_data_plots = hidden_data_plots
        """Sensor data addresses hidden from plot view"""
        self.track_manager = track_manager
        """Database instance"""
        self.track_manager_directory = track_manager_directory
        """Database directory"""
        self.gps_tiles_directory = gps_tiles_directory
        """GPS tiles directory"""
        self.out_dir = out_dir
        """Output directory"""
        self.instance_dir = instance_dir
        """Main process directory"""

        # Check connectivity
        online = check_internet_connectivity()
        
        # Setup logger
        self.setup_logging()

        # Create the Flask app
        self.app = Flask(__name__, template_folder="templates", static_folder='static')

        # Compress responses 
        Compress(self.app)
        
        # Pass configuration to the app so blueprints can access it
        self.app.config.update({
            'INSTANCE_DIRECTORY': self.instance_dir,
            'RM_THESAURUS': self.rm_thesaurus,
            'DATA_THESAURUS': self.data_thesaurus,
            'HIDDEN_DATA_PLOTS': self.hidden_data_plots,
            'LOGGER_FNAME': self.logger_fname,
            'TRACK_MANAGER_DIRECTORY': self.track_manager_directory,
            'TRACK_MANAGER': self.track_manager,
            'LOGGER': self.logger,
            'GPS_TILES_DIRECTORY': self.gps_tiles_directory,
            'ANALYSIS_TRACK': None,
            "SETTINGS_ACTIONS": ACTIONS,
            "CONFIG_DATA": config_dict,
            "ONLINE_MODE": online
        })
        
        # Setup secret key
        self.setup_secret_key()
            
        # Setup routes
        self.setup_routes()
        
    def setup_logging(self):
        # Silence Waitress
        logging.getLogger("waitress").setLevel(logging.ERROR)
        
        # Silence Tornado
        for tlog in [access_log, app_log, gen_log]:
            tlog.setLevel(logging.ERROR)
            tlog.propagate = False

        # Silence werkzeug
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

        # Create the main logger
        self.logger = logging.getLogger("WebApp")
        self.logger.setLevel(logging.DEBUG)

    def setup_secret_key(self):
        """
        Configure a secure secret key for Flask sessions and security.
        
        Priority for secret key sources:
        1. Environment variable (most secure)
        2. Instance-specific file
        3. Generated secure random key (fallback)
        """
        # Get path
        instance_path = os.path.join(self.out_dir, 'instance')
        os.makedirs(instance_path, exist_ok=True)
        secret_key_path = os.path.join(instance_path, 'secret_key')

        # Try environment variable first
        secret_key = os.environ.get('FLASK_SECRET_KEY')

        # If no environment variable, try reading from file
        if not secret_key and os.path.exists(secret_key_path):
            with open(secret_key_path, 'r') as f:
                secret_key = f.read().strip()

        # If no existing key, generate a new one
        if not secret_key:
            secret_key = secrets.token_hex(32)  # 256-bit key
            
            # Save generated key to file for persistence
            with open(secret_key_path, 'w') as f:
                f.write(secret_key)
            
            # Secure the file
            os.chmod(secret_key_path, 0o600)  # Read/write for owner only

        # Configure the app with the secret key
        self.app.secret_key = secret_key

        # Additional security configurations
        self.app.config.update(
            SESSION_COOKIE_SECURE=True,  # Only send cookie over HTTPS
            SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access to session cookie
            SESSION_COOKIE_SAMESITE='Lax',  # Protect against CSRF
        )
        
    def setup_routes(self):
        # Register the monitoring blueprint (and others if created)
        self.app.register_blueprint(monitor_bp)
        self.app.register_blueprint(settings_bp)
        self.app.register_blueprint(log_bp)
        self.app.register_blueprint(save_bp)
        self.app.register_blueprint(database_bp)

    def debug(self, host="0.0.0.0", port=5000, debug=True):
        """
        Start the integrated Werkzeug server for developement.
        """
        self.app.run(host=host, port=port, debug=debug, use_reloader=False)
        
    def serve(self, host="0.0.0.0", port=5000):
        serve(self.app, host=host, port=port)
