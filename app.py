import os
import sys
import toml
import logging
from pathlib import Path

from mothics.database import Database
from mothics.webapp import WebApp
from mothics.helpers import setup_logger


def load_config(path="config.toml"):
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file '{path}' not found.")
    return toml.load(config_path)


if __name__ == "__main__":
    # Fetch configuration file
    config = load_config("config.toml")

    # Setup logger
    logger_fname = config["files"]["logger_fname"]
    setup_logger('logger', fname=logger_fname, silent=False)
    logging.basicConfig(level=logging.INFO)
    
    # Start Database
    out_dir = config["files"]["output_dir"]
    db = Database(directory=out_dir,
                  rm_thesaurus=config["webapp"]["rm_thesaurus"],
                  validation=config["database"]["validation"])
    
    # Build WebApp instance
    app = WebApp(logger_fname=config["files"]["logger_fname"],
                 rm_thesaurus=config["webapp"]["rm_thesaurus"],
                 data_thesaurus=config["webapp"]["data_thesaurus"],
                 hidden_data_plots=config["webapp"]["hidden_data_plots"],
                 track_manager=db,
                 track_manager_directory=out_dir,
                 gps_tiles_directory=config["files"]["tile_dir"],
                 instance_dir=os.path.dirname(sys.modules['__main__'].__file__),
                 out_dir=config["files"]["output_dir"],
                 config_dict=config
                 )
    
    # Run the Flask app
    app.serve(port=config["webapp"]["port"])
