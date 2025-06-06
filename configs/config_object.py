import json
import os


class Paths:
    def __init__(self, config, grid_config, weather_model_config):
        self.grid_folder_path = grid_config['grid_folder_path']
        self.dz_grid_csv_path = grid_config['dz_grid_csv_path']
        self.bathy_path = grid_config['bathy_path']
        self.swiss_topo_path = grid_config['swiss_topo_path']
        self.raw_weather_folder = os.path.join(weather_model_config['raw_results_from_api_folder'], config.lake_name)


class ConfigObject:
    def __init__(self, config_file_path):
        with open(config_file_path, 'r') as file:
            config = json.load(file)

        current_project = config["current_project"]

        self.lake_name = current_project['lake_name']
        self.grid_config_name = current_project['grid_config_name']
        self.start_date = current_project['start_date']
        self.end_date = current_project['end_date']
        self.reference_date = current_project['reference_date']
        self.weather_model = current_project['weather_model']
        self.computer_config = current_project['computer_config']
        self.template_folder = current_project['template_folder']
        self.with_pickup = eval(current_project['with_pickup'])

        self.shoreline_path = config["grid_config"][self.lake_name]["shoreline_path"]

        grid_config = config["grid_config"][self.lake_name][self.grid_config_name]
        weather_model_config = config["weather_model_config"][self.weather_model]
        computer_config = config["computer_config"][self.computer_config]

        # Grid parameters
        self.grid_resolution = grid_config['grid_resolution']
        self.time_step = grid_config['time_step']
        self.x0_epsg2056 = grid_config["x0_epsg2056"]
        self.y0_epsg2056 = grid_config["y0_epsg2056"]
        self.x1_epsg2056 = grid_config["x1_epsg2056"]
        self.y1_epsg2056 = grid_config["y1_epsg2056"]
        self.Nx = grid_config["Nx"]
        self.Ny = grid_config["Ny"]

        # Computer parameters
        self.Px = computer_config["Px"]
        self.Py = computer_config["Py"]
        self.endian_type = computer_config["endian_type"]

        # Lake characteristics
        self.lake_altitude = grid_config["lake_altitude"]

        # Weather model
        self.weather_api_base_url = weather_model_config['base_url']
        self.weather_download_buffer = weather_model_config['buffer']
        self.weather_model_type = weather_model_config['type']

        # Paths
        self.paths = Paths(self, grid_config, weather_model_config)

    def write_metadata_to_file(self, output_file_path):
        with open(output_file_path, 'w') as file:
            file.write("ConfigObject Metadata\n")
            file.write("=====================\n\n")

            for arg, value in vars(self).items():
                if isinstance(value, Paths):
                    file.write(f"{arg}:\n")
                    for path_attr, path_value in vars(value).items():
                        file.write(f"  {path_attr}: {path_value}\n")
                else:
                    file.write(f"{arg}: {value}\n")
